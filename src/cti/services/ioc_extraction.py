"""Deterministic IOC extraction from report text (issue #14).

Pure functions only: no database, no DNS, no network. Document text is data;
nothing in it is interpreted. Every pattern is written so the regex engine
does a bounded amount of work per input character (no nested unbounded
quantifiers; unbounded runs are anchored by a lookbehind so each run is tried
from one start position only).

Pipeline: remove Unicode format characters (category Cf), compose to NFC and
map IDNA dot homoglyphs to ".", refang the text
once (recording where substitutions happened), collapse runs of "." inside
host tokens when at least one dot came from a homoglyph or a defang, then
run the type phases in order — URLs, emails, IPv6, IPv4, hashes, domains —
masking what an earlier phase emitted so a URL's host or an email's domain is
not emitted again. A host (domain, URL host, email domain) never starts or
ends next to a non-ASCII letter or digit: such hosts are taken whole and
IDNA-encoded, or dropped when they do not encode. Literal ".." is left alone,
so a typo is not repaired into a different indicator.
"""

from __future__ import annotations

import bisect
import ipaddress
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from functools import cache, lru_cache
from typing import TYPE_CHECKING

from cti.models.observable import ObservableType

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_SCAN_CHARS = 2_000_000
MAX_CANDIDATES = 1_000
MAX_VALUE_LENGTH = 2048  # observables.value is String(2048)
CONTEXT_RADIUS = 60
CONTEXT_MAX_LENGTH = 200

SUPPORTED_TYPES: tuple[ObservableType, ...] = (
    ObservableType.IP_ADDR,
    ObservableType.DOMAIN_NAME,
    ObservableType.URL,
    ObservableType.FILE_HASH,
    ObservableType.EMAIL_ADDR,
)

URL_SCHEMES = frozenset({"http", "https", "ftp", "sftp"})
FILE_EXTENSION_TLDS = frozenset(
    {
        "exe", "dll", "pdf", "doc", "docx", "xls", "xlsx", "zip", "rar", "js",
        "ps1", "bat", "sh", "py", "txt", "log", "png", "jpg", "gif",
    }
)  # fmt: skip
_URL_TRAILING_PUNCTUATION = ".,;:!?)]}>'\""

# Warning codes (machine-readable, rendered as text by the UI).
W_NON_PUBLIC_IP = "non_public_ip"
W_LOOKS_LIKE_FILENAME = "looks_like_filename"
W_HASH_MD5 = "hash_md5"
W_HASH_SHA1 = "hash_sha1"
W_INVALID_IP = "invalid_ip"
W_INVALID_HASH = "invalid_hash"
W_INVALID_DOMAIN = "invalid_domain"
W_VALUE_TOO_LONG = "value_too_long"


# ── Format characters ────────────────────────────────────────────────────


@cache
def _category_class_body(categories: frozenset[str]) -> str:
    """Regex character-class body of every non-ASCII code point in ``categories``.

    Python's ``re`` has no ``\\p{..}`` classes, so they are built once from
    ``unicodedata`` as compact ranges.
    """
    ranges: list[tuple[int, int]] = []
    for code_point in range(0x80, sys.maxunicode + 1):
        if unicodedata.category(chr(code_point)) in categories:
            if ranges and ranges[-1][1] == code_point - 1:
                ranges[-1] = (ranges[-1][0], code_point)
            else:
                ranges.append((code_point, code_point))
    return "".join(
        re.escape(chr(lo)) if lo == hi else f"{re.escape(chr(lo))}-{re.escape(chr(hi))}"
        for lo, hi in ranges
    )


#: Combining marks. After NFC some remain (no precomposed form exists, or
#: several marks are stacked), and ``\w`` does not match them, so host
#: patterns must include them explicitly or a host would split at the mark.
_MARK_CATEGORIES = frozenset({"Mn", "Mc", "Me"})


def _marks() -> str:
    return _category_class_body(_MARK_CATEGORIES)


def _is_mark(ch: str) -> bool:
    return unicodedata.category(ch) in _MARK_CATEGORIES


@cache
def _format_char_re() -> re.Pattern[str]:
    """One character class of every Unicode ``Cf`` code point (built once)."""
    return re.compile(f"[{_category_class_body(frozenset({'Cf'}))}]+")


#: Characters IDNA treats as label separators: fullwidth full stop,
#: ideographic full stop, halfwidth ideographic full stop.
_DOT_HOMOGLYPHS = str.maketrans({"\uff0e": ".", "\u3002": ".", "\uff61": "."})
# Positions are recorded before translation, so this class must be those same characters.
_HOMOGLYPH_DOT_RE = re.compile("[" + re.escape("".join(map(chr, _DOT_HOMOGLYPHS))) + "]")


# ── Refanging ────────────────────────────────────────────────────────────

_REFANG_RE = re.compile(
    r"\[\.\]|\(\.\)|\{\.\}|\[dot\]|\(dot\)|\{dot\}"
    r"|(?<=[a-z0-9]) dot (?=[a-z0-9])"
    r"|\[://\]|\[:\]"
    r"|\[@\]|\[at\]|\(at\)"
    r"|\bhxxp(?=s?(?:\[:|:))",
    re.IGNORECASE,
)


def _refang_replacement(token: str) -> str:
    lowered = token.lower()
    if lowered == "hxxp":
        return "http"
    if lowered == "[://]":
        return "://"
    if lowered == "[:]":
        return ":"
    if "@" in lowered or "at" in lowered:
        return "@"
    return "."


class _OffsetMap:
    """Maps positions in refanged text back to the original text.

    ``defang_subs`` is the subset of substitutions produced by refanging.
    Dot-run collapsing adds mapping entries that are not defangs, and those
    must not flip ``defanged`` on their own.
    """

    def __init__(
        self,
        substitutions: list[tuple[int, int, int, int]],
        defang_subs: list[tuple[int, int, int, int]] | None = None,
        defang_dots: frozenset[int] | None = None,
    ) -> None:
        # Each entry: (new_start, new_end, orig_start, orig_end), sorted, disjoint.
        self._subs = substitutions
        self._starts = [sub[0] for sub in substitutions]
        if defang_subs is None:
            defang_subs = substitutions
        self._defangs = defang_subs
        self._defang_starts = [sub[0] for sub in defang_subs]
        self.defang_dots = frozenset() if defang_dots is None else defang_dots

    def start(self, pos: int) -> int:
        index = bisect.bisect_right(self._starts, pos) - 1
        if index < 0:
            return pos
        _new_start, new_end, orig_start, orig_end = self._subs[index]
        if pos < new_end:
            return orig_start
        return orig_end + (pos - new_end)

    def end(self, pos: int) -> int:
        if pos <= 0:
            return pos
        index = bisect.bisect_right(self._starts, pos - 1) - 1
        if index < 0:
            return pos
        _new_start, new_end, _orig_start, orig_end = self._subs[index]
        if pos - 1 < new_end:
            return orig_end
        return orig_end + (pos - new_end)

    def defanged(self, start: int, end: int) -> bool:
        index = bisect.bisect_left(self._defang_starts, end) - 1
        return index >= 0 and self._defangs[index][1] > start


def refang(text: str) -> tuple[str, _OffsetMap]:
    parts: list[str] = []
    substitutions: list[tuple[int, int, int, int]] = []
    defang_dots: list[int] = []
    last = 0
    new_length = 0
    for match in _REFANG_RE.finditer(text):
        start, end = match.span()
        parts.append(text[last:start])
        new_length += start - last
        replacement = _refang_replacement(match.group())
        if replacement == ".":
            defang_dots.append(new_length)
        substitutions.append((new_length, new_length + len(replacement), start, end))
        parts.append(replacement)
        new_length += len(replacement)
        last = end
    if not substitutions:
        return text, _OffsetMap([])
    parts.append(text[last:])
    return "".join(parts), _OffsetMap(substitutions, defang_dots=frozenset(defang_dots))


def _prepare_scan_text(text: str) -> tuple[str, frozenset[int]]:
    """Return normalized scan text and indexes of dots that were homoglyphs.

    Indexes refer to the normalized text (after format-character removal and
    NFC), which is also the coordinate space ``refang`` maps back to.
    """
    if text.isascii():
        return text, frozenset()
    text = _format_char_re().sub("", text)
    text = unicodedata.normalize("NFC", text)
    homoglyphs = frozenset(match.start() for match in _HOMOGLYPH_DOT_RE.finditer(text))
    if not homoglyphs:
        return text, homoglyphs
    return text.translate(_DOT_HOMOGLYPHS), homoglyphs


def normalize_scan_text(text: str) -> str:
    """Prepare text for matching so no host can be split into a shorter suffix.

    Removes Unicode format characters (zero-width, bidi controls, BOM, ...),
    composes to NFC so combining marks join their base letter, and maps the
    IDNA dot homoglyphs to ``.``.
    """
    prepared, _homoglyphs = _prepare_scan_text(text)
    return prepared


def _url_host_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Host slice of a URL match, excluding userinfo, port, path, and brackets."""
    separator = text.find("://", start, end)
    if separator == -1:
        return None
    auth_start = separator + 3
    auth_end = auth_start
    while auth_end < end and text[auth_end] not in "/?#":
        auth_end += 1
    if auth_start >= auth_end:
        return None
    at = text.rfind("@", auth_start, auth_end)
    host_start = at + 1 if at != -1 else auth_start
    if host_start >= auth_end:
        return None
    if text[host_start] == "[":
        close = text.find("]", host_start, auth_end)
        host_end = close if close != -1 else auth_end
        host_start += 1
    else:
        colon = text.find(":", host_start, auth_end)
        host_end = colon if colon != -1 else auth_end
    if host_start >= host_end:
        return None
    return host_start, host_end


def _overlaps(
    start: int, end: int, blocked: list[tuple[int, int]], index: int
) -> tuple[bool, int]:
    while index < len(blocked) and blocked[index][1] <= start:
        index += 1
    hit = index < len(blocked) and blocked[index][0] < end
    return hit, index


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _collapsible_host_spans(text: str) -> list[tuple[int, int]]:
    """Hostname slices: URL hosts, email domains, and bare domain or IP runs.

    Path, query, fragment, and URL userinfo are excluded, as is an email
    local part. A dotted path segment is not a host token.
    """
    urls = [(match.start(), match.end()) for match in _URL_RE.finditer(text)]
    spans: list[tuple[int, int]] = []
    for start, end in urls:
        host = _url_host_span(text, start, end)
        if host is not None:
            spans.append(host)

    blocked = list(urls)
    index = 0
    for match in _email_re().finditer(text):
        start, end = match.span()
        overlaps, index = _overlaps(start, end, urls, index)
        if overlaps:
            continue
        at = match.group().rfind("@")
        domain_start = start + at + 1
        if domain_start < end:
            spans.append((domain_start, end))
        blocked.append((start, end))

    blocked = _merge_spans(blocked)
    index = 0
    for match in _domain_run_re().finditer(text):
        start, end = match.span()
        overlaps, index = _overlaps(start, end, blocked, index)
        if overlaps:
            continue
        spans.append((start, end))
    return spans


def _classify_dot_run(
    start: int,
    end: int,
    offsets: _OffsetMap,
    homoglyphs: frozenset[int],
) -> tuple[bool, bool]:
    """Return (should_collapse, run_contains_a_defang_dot)."""
    obfuscated = False
    for pos in range(start, end):
        if pos in offsets.defang_dots:
            return True, True
        if offsets.start(pos) in homoglyphs:
            obfuscated = True
    return obfuscated, False


def _obfuscated_dot_runs(
    text: str,
    offsets: _OffsetMap,
    homoglyphs: frozenset[int],
) -> list[tuple[int, int, bool]]:
    found: list[tuple[int, int, bool]] = []
    for span_start, span_end in _collapsible_host_spans(text):
        dot = text.find(".", span_start, span_end)
        while dot != -1:
            run_end = dot + 1
            while run_end < span_end and text[run_end] == ".":
                run_end += 1
            if run_end - dot >= 2:
                obfuscated, is_defang = _classify_dot_run(dot, run_end, offsets, homoglyphs)
                if obfuscated:
                    found.append((dot, run_end, is_defang))
            dot = text.find(".", run_end, span_end)
    found.sort()
    deduped: list[tuple[int, int, bool]] = []
    last_end = -1
    for start, end, is_defang in found:
        if start < last_end:
            continue
        deduped.append((start, end, is_defang))
        last_end = end
    return deduped


def _apply_dot_collapses(
    text: str,
    offsets: _OffsetMap,
    runs: list[tuple[int, int, bool]],
) -> tuple[str, _OffsetMap]:
    """Replace each run with one '.' and keep original-text coordinates.

    A collapsed dot maps back to the whole run, so ``original`` still shows
    the defang marker. The dot counts as a defang only when the run contained
    one.
    """
    parts: list[str] = []
    mapping: list[tuple[int, int, int, int]] = []
    defangs: list[tuple[int, int, int, int]] = []
    old_subs = offsets._subs
    sub_index = 0
    cursor_old = 0
    cursor_new = 0

    def copy_until(old_end: int) -> None:
        nonlocal cursor_old, cursor_new, sub_index
        if old_end > cursor_old:
            parts.append(text[cursor_old:old_end])
        shift = cursor_new - cursor_old
        while sub_index < len(old_subs) and old_subs[sub_index][0] < old_end:
            new_start, new_end, orig_start, orig_end = old_subs[sub_index]
            if new_start >= cursor_old:
                shifted = (new_start + shift, new_end + shift, orig_start, orig_end)
                mapping.append(shifted)
                defangs.append(shifted)
            sub_index += 1
        cursor_new += old_end - cursor_old
        cursor_old = old_end

    for run_start, run_end, is_defang in runs:
        copy_until(run_start)
        while sub_index < len(old_subs) and old_subs[sub_index][0] < run_end:
            sub_index += 1
        collapsed = (cursor_new, cursor_new + 1, offsets.start(run_start), offsets.end(run_end))
        mapping.append(collapsed)
        if is_defang:
            defangs.append(collapsed)
        parts.append(".")
        cursor_new += 1
        cursor_old = run_end
    copy_until(len(text))
    return "".join(parts), _OffsetMap(mapping, defang_subs=defangs)


def _collapse_obfuscated_host_dots(
    text: str,
    offsets: _OffsetMap,
    homoglyphs: frozenset[int],
) -> tuple[str, _OffsetMap]:
    """Collapse ``..`` inside hosts when a homoglyph or defang produced a dot.

    A fullwidth dot beside ``[.]`` normalizes to ``evil..example.com`` and
    would otherwise fail as an empty label. A literal ``evil..example.com``
    is not rewritten.
    """
    if not homoglyphs and not offsets.defang_dots:
        return text, offsets
    if ".." not in text:
        return text, offsets
    runs = _obfuscated_dot_runs(text, offsets, homoglyphs)
    if not runs:
        return text, offsets
    return _apply_dot_collapses(text, offsets, runs)


# ── Validation helpers ───────────────────────────────────────────────────

_LABEL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _tld_shape_ok(tld: str) -> bool:
    return (tld.isascii() and tld.isalpha() and len(tld) >= 2) or tld.startswith("xn--")


def normalize_domain(value: str) -> str | None:
    """Return the normalized domain, or None when it is not a valid domain."""
    host = value.lower()
    if host.endswith("."):
        host = host[:-1]
    if not host or len(host) > 253 or not host.isascii():
        return None
    labels = host.split(".")
    if len(labels) < 2 or not _tld_shape_ok(labels[-1]):
        return None
    if not all(_LABEL_RE.fullmatch(label) for label in labels):
        return None
    try:
        host.encode("idna")
    except UnicodeError:
        return None
    return host


def idna_host(host: str) -> str | None:
    """IDNA-encode a host with non-ASCII labels; None when it does not encode.

    Labels and the host are length-checked first so the codec (punycode is
    quadratic in label length) only ever sees bounded input.
    """
    if host.isascii():
        return host
    return _idna_encode(host)


@lru_cache(maxsize=4096)  # Reports repeat hosts; the codec is the slow part.
def _idna_encode(host: str) -> str | None:
    if len(host) > 253 or any(len(label) > 63 for label in host.split(".")):
        return None
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def _is_non_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _ip_warnings(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> list[str]:
    return [W_NON_PUBLIC_IP] if _is_non_public(address) else []


def _normalize_url_host(host: str) -> str | None:
    if not host:
        return None
    if host.startswith("["):
        if not host.endswith("]"):
            return None
        try:
            ipaddress.IPv6Address(host[1:-1])
        except ValueError:
            return None
        return host.lower()
    if all(ch.isdigit() or ch == "." for ch in host):
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            return None
        return host
    encoded = idna_host(host)
    if encoded is None or normalize_domain(encoded) is None:
        return None
    return encoded.lower()


_PORT_RE = re.compile(r"(?::[0-9]{1,5})?")


def normalize_url(raw: str) -> str | None:
    """Lowercase scheme and host, keep the rest as written; None when invalid."""
    scheme, separator, rest = raw.partition("://")
    scheme = scheme.lower()
    if not separator or scheme not in URL_SCHEMES:
        return None
    authority_end = len(rest)
    for delimiter in "/?#":
        index = rest.find(delimiter)
        if index != -1:
            authority_end = min(authority_end, index)
    authority, tail = rest[:authority_end], rest[authority_end:]
    userinfo, at, hostport = authority.rpartition("@")
    if hostport.startswith("["):
        close = hostport.find("]")
        if close == -1:
            return None
        host, port = hostport[: close + 1], hostport[close + 1 :]
    else:
        host, colon, port_digits = hostport.partition(":")
        port = colon + port_digits
    if not _PORT_RE.fullmatch(port) or (len(port) > 1 and int(port[1:]) > 65535):
        return None
    normalized_host = _normalize_url_host(host)
    if normalized_host is None:
        return None
    return f"{scheme}://{userinfo}{at}{normalized_host}{port}{tail}"


# ── Candidates ───────────────────────────────────────────────────────────


@dataclass
class Candidate:
    type: ObservableType
    value: str
    original: str
    context: str
    occurrences: int
    defanged: bool
    valid: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    candidates: list[Candidate]  # sorted by (type, value)
    truncated: bool


@dataclass
class _Hit:
    type: ObservableType
    value: str
    valid: bool
    warnings: list[str]
    start: int  # refanged-text offsets
    end: int


@dataclass
class _Acc:
    type: ObservableType
    value: str
    valid: bool
    warnings: list[str]
    position: tuple[int, int]  # (source index, original offset)
    source_index: int
    orig_start: int
    orig_end: int
    defanged: bool
    occurrences: int = 0


_FORMAT_CHARS = frozenset({"Cc", "Cf", "Zl", "Zp"})


def _context(text: str, start: int, end: int) -> str:
    snippet = text[max(0, start - CONTEXT_RADIUS) : min(len(text), end + CONTEXT_RADIUS)]
    cleaned = "".join(" " if unicodedata.category(ch) in _FORMAT_CHARS else ch for ch in snippet)
    return " ".join(cleaned.split())[:CONTEXT_MAX_LENGTH]


def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return text
    parts: list[str] = []
    last = 0
    for start, end in sorted(spans):
        if start < last:
            start = last
        if end <= start:
            continue
        parts.append(text[last:start])
        parts.append(" " * (end - start))
        last = end
    parts.append(text[last:])
    return "".join(parts)


# ── Phases (all run on refanged, dot-collapsed text) ─────────────────────

# Zero-width, bidi-control and other invisible characters end a URL run, so a
# value can never carry hidden or direction-flipping characters.
_URL_RE = re.compile(
    r"\b(?:https?|s?ftp)://"
    r"(?:(?!\]\()[^\s<>\"`\x00-\x1f\x7f-\x9f­​-‏‪-‮⁠-⁯﻿])+",
    re.IGNORECASE,
)


def _phase_urls(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _URL_RE.finditer(text):
        raw = match.group().rstrip(_URL_TRAILING_PUNCTUATION)
        start, end = match.start(), match.start() + len(raw)
        normalized = normalize_url(raw)
        if normalized is None:
            continue  # Invalid host: not a URL; its parts may still be found below.
        spans.append((start, end))
        if len(normalized) > MAX_VALUE_LENGTH:
            hits.append(
                _Hit(
                    ObservableType.URL,
                    normalized[:MAX_VALUE_LENGTH],
                    False,
                    [W_VALUE_TOO_LONG],
                    start,
                    end,
                )
            )
        else:
            hits.append(_Hit(ObservableType.URL, normalized, True, [], start, end))
    return hits, spans


_EMAIL_LOCAL = r"A-Za-z0-9._%+\-"
# Domain characters are any letter or digit (``[^\W_]``), dot or hyphen, so a
# non-ASCII label is taken whole and IDNA-encoded rather than cut short.
# Combining marks are host characters too (see ``_MARK_CATEGORIES``).


@cache
def _email_re() -> re.Pattern[str]:
    return re.compile(
        rf"(?<![{_EMAIL_LOCAL}])[{_EMAIL_LOCAL}]{{1,64}}@(?:[^\W_]|[.\-{_marks()}]){{1,253}}"
    )


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or _is_mark(ch)


def _is_host_char(ch: str) -> bool:
    return _is_word_char(ch) or ch in ".-"


def _phase_emails(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _email_re().finditer(text):
        start, end = match.span()
        if end < len(text) and _is_host_char(text[end]):
            continue  # Domain part longer than any valid hostname.
        if start > 0 and _is_word_char(text[start - 1]):
            # The ASCII-only local part began mid-word ("jürgen@" would match
            # as "rgen@"). Never emit a truncated address; the host can still
            # surface from the domain phase.
            continue
        local, _, domain = match.group().partition("@")
        stripped_local = local.lstrip(".")
        start += len(local) - len(stripped_local)
        stripped_domain = domain.rstrip(".")
        end -= len(domain) - len(stripped_domain)
        if not stripped_local or stripped_local.endswith("."):
            continue
        encoded = idna_host(stripped_domain)
        normalized = normalize_domain(encoded) if encoded is not None else None
        if normalized is None:
            continue
        spans.append((start, end))
        hits.append(
            _Hit(ObservableType.EMAIL_ADDR, f"{stripped_local}@{normalized}", True, [], start, end)
        )
    return hits, spans


_IPV6_RE = re.compile(r"(?<![0-9A-Za-z:.])(?=[0-9A-Fa-f.]*:)[0-9A-Fa-f:.]{2,}(?![0-9A-Za-z:.])")


def _phase_ipv6(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _IPV6_RE.finditer(text):
        token = match.group().rstrip(".")
        # Require two colons and a digit: skips times, "a::b" scope operators, etc.
        if token.count(":") < 2 or not any(ch.isdigit() for ch in token):
            continue
        try:
            address = ipaddress.IPv6Address(token)
        except ValueError:
            continue
        start = match.start()
        end = start + len(token)
        spans.append((start, end))
        hits.append(
            _Hit(ObservableType.IP_ADDR, str(address), True, _ip_warnings(address), start, end)
        )
    return hits, spans


_IPV4_RE = re.compile(
    r"(?<![0-9A-Za-z.])[0-9]{1,3}(?:\.[0-9]{1,3}){3}(?![0-9A-Za-z\-]|\.[0-9A-Za-z])"
)


def _phase_ipv4(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _IPV4_RE.finditer(text):
        token = match.group()
        start, end = match.span()
        spans.append((start, end))
        try:
            address = ipaddress.IPv4Address(token)
        except ValueError:
            hits.append(_Hit(ObservableType.IP_ADDR, token, False, [W_INVALID_IP], start, end))
            continue
        hits.append(
            _Hit(ObservableType.IP_ADDR, str(address), True, _ip_warnings(address), start, end)
        )
    return hits, spans


_HASH_RE = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,64}(?![0-9A-Fa-f])")
_HASH_WARNINGS = {32: [W_HASH_MD5], 40: [W_HASH_SHA1], 64: []}


def _phase_hashes(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _HASH_RE.finditer(text):
        token = match.group()
        if len(token) not in _HASH_WARNINGS:
            continue
        start, end = match.span()
        spans.append((start, end))
        value = token.lower()
        if len(set(value)) == 1:
            hits.append(_Hit(ObservableType.FILE_HASH, value, False, [W_INVALID_HASH], start, end))
        else:
            hits.append(
                _Hit(
                    ObservableType.FILE_HASH,
                    value,
                    True,
                    list(_HASH_WARNINGS[len(token)]),
                    start,
                    end,
                )
            )
    return hits, spans


# ``\w`` is Unicode-aware: a run spans every adjacent letter or digit, ASCII or
# not, plus combining marks (which ``\w`` misses), so it can never begin or end
# next to a non-ASCII letter, digit, or mark.
@cache
def _domain_run_re() -> re.Pattern[str]:
    m = _marks()
    return re.compile(rf"(?<![\w.\-{m}])[\w\-{m}]*\.[\w.\-{m}]*")


def _phase_domains(text: str, offsets: _OffsetMap) -> list[_Hit]:
    hits: list[_Hit] = []
    for match in _domain_run_re().finditer(text):
        run = match.group()
        token = run.strip(".")
        if not token or "_" in token:
            continue
        start = match.start() + (len(run) - len(run.lstrip(".")))
        end = start + len(token)
        if not token.isascii():
            encoded = idna_host(token)
            if encoded is None:
                continue  # Never emit part of a host that does not encode.
            token = encoded
        labels = token.split(".")
        tld = labels[-1].lower()
        if len(labels) < 2 or not _tld_shape_ok(tld):
            continue  # Not domain-shaped ("e.g", "v1.2", "1.2.3.4").
        defanged = offsets.defanged(start, end)
        warnings: list[str] = []
        if tld in FILE_EXTENSION_TLDS:
            if not defanged:
                continue  # "invoice.pdf" noise.
            warnings.append(W_LOOKS_LIKE_FILENAME)
        normalized = normalize_domain(token)
        if normalized is None:
            hits.append(
                _Hit(
                    ObservableType.DOMAIN_NAME,
                    token.lower()[:MAX_VALUE_LENGTH],
                    False,
                    [W_INVALID_DOMAIN],
                    start,
                    end,
                )
            )
        else:
            hits.append(_Hit(ObservableType.DOMAIN_NAME, normalized, True, warnings, start, end))
    return hits


def _scan(text: str, homoglyphs: frozenset[int]) -> tuple[list[_Hit], _OffsetMap]:
    refanged, offsets = refang(text)
    refanged, offsets = _collapse_obfuscated_host_dots(refanged, offsets, homoglyphs)
    hits: list[_Hit] = []
    for phase in (_phase_urls, _phase_emails, _phase_ipv6, _phase_ipv4, _phase_hashes):
        phase_hits, spans = phase(refanged)
        hits.extend(phase_hits)
        refanged = _mask(refanged, spans)
    hits.extend(_phase_domains(refanged, offsets))
    return hits, offsets


# ── Entry point ──────────────────────────────────────────────────────────


def extract(texts: Sequence[str]) -> ExtractionResult:
    """Extract candidates from document texts, in source order.

    At most ``MAX_SCAN_CHARS`` characters are scanned across all texts and at
    most ``MAX_CANDIDATES`` unique candidates (the earliest in the document)
    are returned; either limit sets ``truncated``.
    """
    truncated = False
    remaining = MAX_SCAN_CHARS
    scanned: list[str] = []
    accumulated: dict[tuple[ObservableType, str], _Acc] = {}

    for source_index, full_text in enumerate(texts):
        if remaining <= 0:
            if full_text:
                truncated = True
            scanned.append("")
            continue
        text = full_text
        if len(text) > remaining:
            text = text[:remaining]
            truncated = True
        # NFC can expand text (up to 3x per code point), so the budget is
        # enforced again on the normalized text that is actually scanned.
        text, homoglyphs = _prepare_scan_text(text)
        if len(text) > remaining:
            text = text[:remaining]
            truncated = True
            homoglyphs = frozenset(pos for pos in homoglyphs if pos < len(text))
        remaining -= len(text)
        scanned.append(text)

        hits, offsets = _scan(text, homoglyphs)
        for hit in hits:
            orig_start = offsets.start(hit.start)
            orig_end = offsets.end(hit.end)
            key = (hit.type, hit.value)
            position = (source_index, orig_start)
            acc = accumulated.get(key)
            if acc is None:
                acc = _Acc(
                    type=hit.type,
                    value=hit.value,
                    valid=hit.valid,
                    warnings=hit.warnings,
                    position=position,
                    source_index=source_index,
                    orig_start=orig_start,
                    orig_end=orig_end,
                    defanged=offsets.defanged(hit.start, hit.end),
                )
                accumulated[key] = acc
            elif position < acc.position:
                acc.position = position
                acc.source_index = source_index
                acc.orig_start = orig_start
                acc.orig_end = orig_end
                acc.defanged = offsets.defanged(hit.start, hit.end)
            acc.occurrences += 1

    entries = list(accumulated.values())
    if len(entries) > MAX_CANDIDATES:
        truncated = True
        entries.sort(key=lambda entry: entry.position)
        entries = entries[:MAX_CANDIDATES]

    candidates = []
    for entry in entries:
        source = scanned[entry.source_index]
        candidates.append(
            Candidate(
                type=entry.type,
                value=entry.value,
                original=source[entry.orig_start : entry.orig_end][:MAX_VALUE_LENGTH],
                context=_context(source, entry.orig_start, entry.orig_end),
                occurrences=entry.occurrences,
                defanged=entry.defanged,
                valid=entry.valid,
                warnings=list(entry.warnings),
            )
        )
    candidates.sort(key=lambda candidate: (candidate.type.value, candidate.value))
    return ExtractionResult(candidates=candidates, truncated=truncated)
