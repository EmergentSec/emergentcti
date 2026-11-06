"""Sandboxed PDF text extraction (issue #24)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time

import pytest

from cti.services import ioc_extraction, pdf_text
from tests.pdf_samples import (
    MALFORMED_PDF,
    encrypted_pdf,
    image_only_pdf,
    text_pdf,
)

REPORT_PAGE = "Exfil to drop[.]example and 185.220.101.42 observed.\nSecond line (escaped)."


async def test_text_pdf_feeds_the_ioc_extractor_with_context() -> None:
    result = await pdf_text.extract_text(text_pdf(REPORT_PAGE))
    assert result.reason is None
    assert result.text is not None
    candidates = ioc_extraction.extract([result.text]).candidates
    by_value = {c.value: c for c in candidates}
    assert set(by_value) == {"drop.example", "185.220.101.42"}
    assert by_value["drop.example"].defanged
    assert "Exfil to" in by_value["drop.example"].context


async def test_multi_page_text_is_joined() -> None:
    result = await pdf_text.extract_text(
        text_pdf("first page evil-one.example", "second evil-two.example")
    )
    assert result.text is not None
    assert "evil-one.example" in result.text
    assert "evil-two.example" in result.text


@pytest.mark.parametrize("footer", [None, "Page {} of 5"])
async def test_image_only_pdf_has_no_text_layer(footer: str | None) -> None:
    result = await pdf_text.extract_text(image_only_pdf(5, footer=footer))
    assert result == pdf_text.PdfTextResult(None, pdf_text.REASON_NO_TEXT_LAYER)


async def test_encrypted_pdf_fails_closed_even_with_empty_user_password() -> None:
    result = await pdf_text.extract_text(encrypted_pdf("secret evil.example body text"))
    assert result == pdf_text.PdfTextResult(None, pdf_text.REASON_ENCRYPTED)


@pytest.mark.parametrize(
    "data",
    [
        MALFORMED_PDF,
        text_pdf("hello evil.example world")[:200],  # truncated mid-object
        b"%PDF-",
        b"not a pdf at all",
    ],
)
async def test_malformed_pdf_fails_closed(data: bytes) -> None:
    result = await pdf_text.extract_text(data)
    assert result == pdf_text.PdfTextResult(None, pdf_text.REASON_MALFORMED)


async def test_oversized_pdf_is_rejected_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    data = text_pdf(REPORT_PAGE)
    monkeypatch.setattr(pdf_text, "MAX_PDF_BYTES", len(data) - 1)

    def no_worker(*_: object, **__: object) -> None:
        raise AssertionError("the worker must not start")

    monkeypatch.setattr(pdf_text.asyncio, "create_subprocess_exec", no_worker)
    assert await pdf_text.extract_text(data) == pdf_text.PdfTextResult(
        None, pdf_text.REASON_TOO_LARGE
    )


async def test_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_text, "MAX_PAGES", 2)
    result = await pdf_text.extract_text(text_pdf("one evil.example", "two", "three"))
    assert result == pdf_text.PdfTextResult(None, pdf_text.REASON_TOO_MANY_PAGES)


async def test_text_is_capped_at_the_scan_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_text, "MAX_CHARS", 40)
    page = "x" * 60 + " evil.example"
    result = await pdf_text.extract_text(text_pdf(page, page, page))
    assert result.text is not None
    assert len(result.text) == 40


async def test_hung_worker_is_killed_at_the_wall_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_text, "WALL_TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(
        pdf_text, "_worker_args", lambda: [sys.executable, "-c", "import time; time.sleep(60)"]
    )
    started = time.monotonic()
    result = await pdf_text.extract_text(text_pdf(REPORT_PAGE))
    assert result == pdf_text.PdfTextResult(None, pdf_text.REASON_TIMEOUT)
    assert time.monotonic() - started < 10


async def test_worker_gets_no_inherited_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret@db/cti")
    script = (
        "import json, os, sys; "
        "sys.stdout.write(json.dumps({'ok': True, 'text': json.dumps(dict(os.environ))}))"
    )
    monkeypatch.setattr(pdf_text, "_worker_args", lambda: [sys.executable, "-c", script])
    result = await pdf_text.extract_text(text_pdf(REPORT_PAGE))
    assert result.text is not None
    assert set(json.loads(result.text)) <= {"LC_ALL", "LC_CTYPE"}


@pytest.mark.parametrize(
    ("returncode", "stdout", "reason"),
    [
        (-24, b"", pdf_text.REASON_TIMEOUT),  # SIGXCPU: hit the CPU limit
        (-9, b"", pdf_text.REASON_TIMEOUT),
        (1, b"", pdf_text.REASON_FAILED),
        (0, b"", pdf_text.REASON_FAILED),
        (0, b"not json", pdf_text.REASON_FAILED),
        (0, b"[]", pdf_text.REASON_FAILED),
        (0, b'{"ok": false, "reason": "something_else"}', pdf_text.REASON_FAILED),
        (0, b'{"ok": false, "reason": "pdf_too_complex"}', pdf_text.REASON_TOO_COMPLEX),
        (0, b'{"ok": true, "text": 5}', pdf_text.REASON_FAILED),
    ],
)
def test_worker_output_maps_to_a_known_reason(returncode: int, stdout: bytes, reason: str) -> None:
    assert pdf_text._parse_output(returncode, stdout) == pdf_text.PdfTextResult(None, reason)


def _load_worker() -> object:
    spec = importlib.util.spec_from_file_location("pdf_worker_under_test", pdf_text.WORKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("event", "args"),
    [
        ("socket.connect", (None, ("127.0.0.1", 80))),
        ("socket.getaddrinfo", ("example.com", 80, 0, 0, 0)),
        ("subprocess.Popen", ("sh", ["sh"], None, None)),
        ("os.system", (b"id",)),
        ("os.posix_spawn", ("sh", ["sh"], {})),
        ("open", ("/tmp/out", "w", os.O_WRONLY | os.O_CREAT)),
        ("open", ("/tmp/out", None, os.O_RDWR)),
    ],
)
def test_worker_audit_hook_blocks_network_processes_and_writes(
    event: str, args: tuple[object, ...]
) -> None:
    worker = _load_worker()
    with pytest.raises(PermissionError):
        worker._audit(event, args)  # type: ignore[attr-defined]


def test_worker_audit_hook_allows_reads() -> None:
    worker = _load_worker()
    worker._audit("open", ("/x/module.py", "r", os.O_RDONLY))  # type: ignore[attr-defined]


def test_audit_hook_stops_a_real_connection_attempt() -> None:
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('w', {str(pdf_text.WORKER_PATH)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "sys.addaudithook(m._audit)\n"
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=1)\n"
        "except PermissionError:\n"
        "    print('blocked')\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=30, check=True
    )
    assert out.stdout.strip() == "blocked"
