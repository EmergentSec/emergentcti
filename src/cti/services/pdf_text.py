"""Bounded text extraction from PDF attachments (issue #24).

Parsing runs in a short-lived child process (``_pdf_text_worker.py``) so a
hostile or pathological PDF can exhaust only that child's memory and CPU and
never stall the API's event loop. The child gets an empty environment (no
database URL, keys or other secrets), resource limits, and an audit hook that
blocks network and process creation. The parent enforces a wall-clock
timeout and caps how many children run at once.

Every failure maps to a specific ``unsupported`` reason. Nothing raises.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import weakref
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

WORKER_PATH = Path(__file__).with_name("_pdf_text_worker.py")

# Limits. The upload limit (REPORT_MAX_UPLOAD_BYTES) is configurable, so the
# parser keeps its own byte ceiling.
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PAGES = 500
MAX_CHARS = 2_000_000  # Same as the IOC extractor's scan budget.
MEMORY_LIMIT_BYTES = 768 * 1024 * 1024
CPU_LIMIT_SECONDS = 20
WALL_TIMEOUT_SECONDS = 30.0
MAX_CONCURRENT = 2
# Fewer non-whitespace characters than this per page on average means the
# PDF is (mostly) scanned images: page numbers or a header, but no body text.
MIN_CHARS_PER_PAGE = 16
# JSON of MAX_CHARS characters, worst case 4 UTF-8 bytes each, plus framing.
_MAX_OUTPUT_BYTES = MAX_CHARS * 4 + 64 * 1024

REASON_NO_TEXT_LAYER = "pdf_no_text_layer"
REASON_ENCRYPTED = "pdf_encrypted"
REASON_MALFORMED = "pdf_malformed"
REASON_TOO_LARGE = "pdf_too_large"
REASON_TOO_MANY_PAGES = "pdf_too_many_pages"
REASON_TOO_COMPLEX = "pdf_too_complex"
REASON_TIMEOUT = "pdf_extraction_timeout"
REASON_FAILED = "pdf_extraction_failed"

_WORKER_REASONS = frozenset(
    {
        REASON_NO_TEXT_LAYER,
        REASON_ENCRYPTED,
        REASON_MALFORMED,
        REASON_TOO_MANY_PAGES,
        REASON_TOO_COMPLEX,
    }
)

_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


@dataclass(frozen=True)
class PdfTextResult:
    text: str | None
    reason: str | None = None


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = _semaphores[loop] = asyncio.Semaphore(MAX_CONCURRENT)
    return semaphore


def _worker_args() -> list[str]:
    return [
        sys.executable,
        "-I",  # Ignore PYTHON* env vars, user site and the current directory.
        str(WORKER_PATH),
        str(MAX_PAGES),
        str(MAX_CHARS),
        str(MEMORY_LIMIT_BYTES),
        str(CPU_LIMIT_SECONDS),
        str(MIN_CHARS_PER_PAGE),
    ]


async def extract_text(data: bytes) -> PdfTextResult:
    """Return the PDF's text, or a reason it can't be read. Never raises."""
    if len(data) > MAX_PDF_BYTES:
        return PdfTextResult(None, REASON_TOO_LARGE)
    if not data.startswith(b"%PDF-"):
        return PdfTextResult(None, REASON_MALFORMED)
    async with _semaphore():
        return await _run_worker(data)


async def _run_worker(data: bytes) -> PdfTextResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            *_worker_args(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={"LC_ALL": "C.UTF-8"},  # Nothing inherited: no secrets reach the parser.
            close_fds=True,
        )
    except OSError:
        logger.exception("Could not start the PDF text worker")
        return PdfTextResult(None, REASON_FAILED)

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(data), WALL_TIMEOUT_SECONDS)
    except TimeoutError:
        _kill(proc)
        await proc.wait()
        return PdfTextResult(None, REASON_TIMEOUT)
    except BaseException:
        # Cancelled (client went away) or a pipe error: never leave the child running.
        _kill(proc)
        with contextlib.suppress(Exception):
            await asyncio.shield(proc.wait())
        raise

    return _parse_output(proc.returncode, stdout)


def _kill(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


def _parse_output(returncode: int | None, stdout: bytes) -> PdfTextResult:
    if returncode is not None and returncode < 0:
        # Killed by a signal: SIGXCPU/SIGKILL means it hit the CPU limit.
        return PdfTextResult(None, REASON_TIMEOUT)
    if returncode != 0 or not stdout or len(stdout) > _MAX_OUTPUT_BYTES:
        logger.warning("PDF text worker failed (exit %s, %d bytes)", returncode, len(stdout))
        return PdfTextResult(None, REASON_FAILED)
    try:
        payload = json.loads(stdout)
    except ValueError:
        return PdfTextResult(None, REASON_FAILED)
    if not isinstance(payload, dict):
        return PdfTextResult(None, REASON_FAILED)
    if payload.get("ok") is True and isinstance(payload.get("text"), str):
        return PdfTextResult(payload["text"])
    reason = payload.get("reason")
    return PdfTextResult(None, reason if reason in _WORKER_REASONS else REASON_FAILED)
