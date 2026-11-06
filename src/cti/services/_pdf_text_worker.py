"""Sandboxed PDF text extraction child process (issue #24).

Run only by ``cti.services.pdf_text`` as ``python -I <this file> <args>``. It
reads PDF bytes from stdin and writes one JSON object to stdout:
``{"ok": true, "text": ..., "pages": n}`` or ``{"ok": false, "reason": ...}``.

It imports only the standard library and pypdf (never ``cti``), so the child
never loads app settings or secrets. Before touching the input it:

- caps address space, CPU time and core dumps, and forbids file writes;
- installs an audit hook that refuses network, process creation and
  write-mode opens.

pypdf does not execute JavaScript, render, or resolve external references.
The limits are defence in depth against parser bugs, not the primary control.
"""

from __future__ import annotations

import io
import json
import resource
import signal
import sys

sys.dont_write_bytecode = True

_BLOCKED_EVENT_PREFIXES = (
    "socket.",
    "subprocess.",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.forkpty",
    "pty.",
    "urllib.",
    "http.",
    "ftplib.",
    "smtplib.",
    "ctypes.",
    "webbrowser.",
)
_WRITE_FLAGS = 0o1 | 0o2 | 0o100 | 0o1000 | 0o2000  # O_WRONLY O_RDWR O_CREAT O_TRUNC O_APPEND


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event.startswith(_BLOCKED_EVENT_PREFIXES):
        raise PermissionError(f"blocked in PDF sandbox: {event}")
    if event == "open" and len(args) >= 3:
        mode, flags = args[1], args[2]
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            raise PermissionError("blocked in PDF sandbox: write open")
        if isinstance(flags, int) and flags & _WRITE_FLAGS:
            raise PermissionError("blocked in PDF sandbox: write open")


def _limit(kind: int, value: int) -> None:
    _soft, hard = resource.getrlimit(kind)
    if hard != resource.RLIM_INFINITY:
        value = min(value, hard)
    resource.setrlimit(kind, (value, value if hard == resource.RLIM_INFINITY else hard))


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


def _fail(reason: str) -> int:
    _emit({"ok": False, "reason": reason})
    return 0


def main(argv: list[str]) -> int:
    max_pages, max_chars, memory_bytes, cpu_seconds, min_chars_per_page = (
        int(value) for value in argv[1:6]
    )

    # A write past RLIMIT_FSIZE should fail with EFBIG, not kill us with SIGXFSZ.
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    _limit(resource.RLIMIT_CORE, 0)
    _limit(resource.RLIMIT_FSIZE, 0)
    _limit(resource.RLIMIT_CPU, cpu_seconds)
    _limit(resource.RLIMIT_AS, memory_bytes)

    data = sys.stdin.buffer.read()

    # Import before arming the hook (imports open files read-only, which is
    # allowed anyway, but keep the hook's surface to the parsing itself).
    from pypdf import PdfReader
    from pypdf.errors import FileNotDecryptedError, PyPdfError

    sys.addaudithook(_audit)

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            return _fail("pdf_encrypted")
        page_count = len(reader.pages)
        if page_count == 0:
            return _fail("pdf_malformed")
        if page_count > max_pages:
            return _fail("pdf_too_many_pages")

        parts: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
            total += len(text) + 1
            if total >= max_chars:
                break  # The IOC extractor's scan budget would drop the rest.
        text = "\n".join(parts)[:max_chars]
    except MemoryError:
        return _fail("pdf_too_complex")
    except FileNotDecryptedError:
        return _fail("pdf_encrypted")
    except (PyPdfError, RecursionError):
        return _fail("pdf_malformed")
    except Exception:
        # Fail closed: any parser surprise is a malformed document.
        return _fail("pdf_malformed")

    # Reaching the budget proves there is a text layer; otherwise measure it.
    meaningful = sum(1 for ch in text if not ch.isspace())
    if total < max_chars and meaningful < min_chars_per_page * page_count:
        return _fail("pdf_no_text_layer")

    _emit({"ok": True, "text": text, "pages": page_count})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
