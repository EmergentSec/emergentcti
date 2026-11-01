"""Deterministic IOC extraction from report text (issue #14).

Pure functions only: no database, no DNS, no network. Document text is data;
nothing in it is interpreted. Every pattern is written so the regex engine
does a bounded amount of work per input character (no nested unbounded
quantifiers; unbounded runs are anchored by a lookbehind so each run is tried
from one start position only).

Pipeline: refang the text once (recording where substitutions happened), then
run the type phases in order — URLs, emails, IPv6, IPv4, hashes, domains —
masking what an earlier phase emitted so a URL's host or an email's domain is
not emitted again.
"""

from __future__ import annotations

import bisect
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
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
    """Maps positions in refanged text back to the original text."""

    def __init__(self, substitutions: list[tuple[int, int, int, int]]) -> None:
        # Each entry: (new_start, new_end, orig_start, orig_end), sorted, disjoint.
        self._subs = substitutions
        self._starts = [sub[0] for sub in substitutions]

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
        index = bisect.bisect_left(self._starts, end) - 1
        return index >= 0 and self._subs[index][1] > start


def refang(text: str) -> tuple[str, _OffsetMap]:
    parts: list[str] = []
    substitutions: list[tuple[int, int, int, int]] = []
    last = 0
    new_length = 0
    for match in _REFANG_RE.finditer(text):
        start, end = match.span()
        parts.append(text[last:start])
        new_length += start - last
        replacement = _refang_replacement(match.group())
        substitutions.append((new_length, new_length + len(replacement), start, end))
        parts.append(replacement)
        new_length += len(replacement)
        last = end
    if not substitutions:
        return text, _OffsetMap([])
    parts.append(text[last:])
    return "".join(parts), _OffsetMap(substitutions)


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
    if normalize_domain(host) is None:
        return None
    return host.lower()


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


# ── Phases (all run on refanged text) ────────────────────────────────────

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
_HOST_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-")
_EMAIL_RE = re.compile(rf"(?<![{_EMAIL_LOCAL}])[{_EMAIL_LOCAL}]{{1,64}}@[A-Za-z0-9.\-]{{1,253}}")


def _phase_emails(text: str) -> tuple[list[_Hit], list[tuple[int, int]]]:
    hits: list[_Hit] = []
    spans: list[tuple[int, int]] = []
    for match in _EMAIL_RE.finditer(text):
        start, end = match.span()
        if end < len(text) and text[end] in _HOST_CHARS:
            continue  # Domain part longer than any valid hostname.
        local, _, domain = match.group().partition("@")
        stripped_local = local.lstrip(".")
        start += len(local) - len(stripped_local)
        stripped_domain = domain.rstrip(".")
        end -= len(domain) - len(stripped_domain)
        if not stripped_local or stripped_local.endswith("."):
            continue
        normalized = normalize_domain(stripped_domain)
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


_DOMAIN_RUN_RE = re.compile(r"(?<![A-Za-z0-9._\-])[A-Za-z0-9_\-]*\.[A-Za-z0-9._\-]*")


def _phase_domains(text: str, offsets: _OffsetMap) -> list[_Hit]:
    hits: list[_Hit] = []
    for match in _DOMAIN_RUN_RE.finditer(text):
        run = match.group()
        token = run.strip(".")
        if not token or "_" in token:
            continue
        start = match.start() + (len(run) - len(run.lstrip(".")))
        end = start + len(token)
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


def _scan(text: str) -> tuple[list[_Hit], _OffsetMap]:
    refanged, offsets = refang(text)
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
        remaining -= len(text)
        scanned.append(text)

        hits, offsets = _scan(text)
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
