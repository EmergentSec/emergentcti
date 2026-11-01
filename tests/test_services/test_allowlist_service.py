"""Allowlist canonicalization and matching rules."""

from __future__ import annotations

import uuid

import pytest

from cti.models.allowlist import AllowlistEntry, AllowlistKind
from cti.models.observable import ObservableType
from cti.services.allowlist_service import (
    AllowlistMatcher,
    AllowlistValidationError,
    canonicalize_entry,
)

IP = ObservableType.IP_ADDR
DOMAIN = ObservableType.DOMAIN_NAME
URL = ObservableType.URL
EMAIL = ObservableType.EMAIL_ADDR
HASH = ObservableType.FILE_HASH


def entry(
    kind: AllowlistKind, value: str, obs_type: ObservableType | None = None
) -> AllowlistEntry:
    canonical, canonical_type = canonicalize_entry(kind, value, obs_type)
    return AllowlistEntry(
        id=uuid.uuid4(), kind=kind, value=canonical, observable_type=canonical_type, reason="r"
    )


def matcher(*entries: AllowlistEntry) -> AllowlistMatcher:
    return AllowlistMatcher(entries)


# ── canonicalization ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kind", "value", "obs_type", "expected"),
    [
        (AllowlistKind.CIDR, "10.1.2.3/8", None, ("10.0.0.0/8", IP)),
        (AllowlistKind.CIDR, " 192.168.1.0/24 ", IP, ("192.168.1.0/24", IP)),
        (AllowlistKind.CIDR, "8.8.8.8", None, ("8.8.8.8/32", IP)),
        (AllowlistKind.CIDR, "2001:0DB8:0000::1/32", None, ("2001:db8::/32", IP)),
        (AllowlistKind.DOMAIN_SUFFIX, " Example.COM. ", None, ("example.com", DOMAIN)),
        (AllowlistKind.DOMAIN_SUFFIX, "internal", DOMAIN, ("internal", DOMAIN)),
        (AllowlistKind.EXACT, "WWW.Example.com.", DOMAIN, ("www.example.com", DOMAIN)),
        (AllowlistKind.EXACT, "2001:0db8:0000:0000:0000:0000:0000:0001", IP, ("2001:db8::1", IP)),
        (AllowlistKind.EXACT, "010.0.0.1", URL, ("010.0.0.1", URL)),
        # Literal types are stored verbatim: no trimming or case folding.
        (AllowlistKind.EXACT, " http://Example.com/Path ", URL, (" http://Example.com/Path ", URL)),
        (AllowlistKind.EXACT, " 10.0.0.5 ", IP, ("10.0.0.5", IP)),
        (AllowlistKind.EXACT, "ABCDEF", HASH, ("ABCDEF", HASH)),
    ],
)
def test_canonicalize_valid(kind, value, obs_type, expected) -> None:
    assert canonicalize_entry(kind, value, obs_type) == expected


@pytest.mark.parametrize(
    ("kind", "value", "obs_type"),
    [
        (AllowlistKind.EXACT, "1.2.3.4", None),  # exact requires a type
        (AllowlistKind.EXACT, "   ", URL),
        (AllowlistKind.EXACT, "not-an-ip", IP),
        (AllowlistKind.EXACT, "999.1.1.1", IP),
        (AllowlistKind.EXACT, "10.0.0.0/24", IP),  # ranges belong to the cidr kind
        (AllowlistKind.EXACT, "2001:db8::/32", IP),
        (AllowlistKind.EXACT, "bad domain.com", DOMAIN),
        (AllowlistKind.CIDR, "example.com", None),
        (AllowlistKind.CIDR, "10.0.0.0/33", None),
        (AllowlistKind.CIDR, "2001:db8::/129", None),
        (AllowlistKind.CIDR, "10.0.0.0/8", DOMAIN),  # CIDR is ip-addr only
        (AllowlistKind.DOMAIN_SUFFIX, "example.com", URL),  # suffix is domain-name only
        (AllowlistKind.DOMAIN_SUFFIX, "*.example.com", None),
        (AllowlistKind.DOMAIN_SUFFIX, ".example.com", None),
        (AllowlistKind.DOMAIN_SUFFIX, "example..com", None),
        (AllowlistKind.DOMAIN_SUFFIX, "https://example.com", None),
        (AllowlistKind.DOMAIN_SUFFIX, "example.com/path", None),
        (AllowlistKind.DOMAIN_SUFFIX, "user@example.com", None),
        (AllowlistKind.DOMAIN_SUFFIX, "exa mple.com", None),
        (AllowlistKind.DOMAIN_SUFFIX, ".", None),
        (AllowlistKind.DOMAIN_SUFFIX, "1.2.3.4", None),
        (AllowlistKind.DOMAIN_SUFFIX, "a" * 64 + ".com", None),
    ],
)
def test_canonicalize_invalid(kind, value, obs_type) -> None:
    with pytest.raises(AllowlistValidationError):
        canonicalize_entry(kind, value, obs_type)


# ── exact ────────────────────────────────────────────────────────────────


def test_exact_is_type_specific() -> None:
    m = matcher(entry(AllowlistKind.EXACT, "example.com", DOMAIN))
    assert m.is_allowlisted(DOMAIN, "example.com")
    # Same literal under another type is a different indicator.
    assert not m.is_allowlisted(URL, "example.com")
    assert not m.is_allowlisted(EMAIL, "example.com")


def test_exact_domain_normalizes_but_does_not_match_subdomains() -> None:
    m = matcher(entry(AllowlistKind.EXACT, "Example.com.", DOMAIN))
    assert m.is_allowlisted(DOMAIN, "EXAMPLE.COM")
    assert m.is_allowlisted(DOMAIN, "example.com.")
    assert not m.is_allowlisted(DOMAIN, "www.example.com")


def test_exact_ip_canonicalizes_both_sides() -> None:
    m = matcher(entry(AllowlistKind.EXACT, "2001:db8::1", IP))
    assert m.is_allowlisted(IP, "2001:0DB8:0000:0000:0000:0000:0000:0001")
    assert not m.is_allowlisted(IP, "2001:db8::2")


def test_exact_ip_suppresses_range_indicators_that_contain_it() -> None:
    v4 = entry(AllowlistKind.EXACT, "10.0.0.5", IP)
    v6 = entry(AllowlistKind.EXACT, "2001:db8::5", IP)
    m = matcher(v4, v6)
    # Exporting a range that covers a protected address would still block it.
    assert m.match(IP, "10.0.0.0/24") == [v4.id]
    assert m.match(IP, "10.0.0.5/32") == [v4.id]
    assert m.match(IP, "0.0.0.0/0") == [v4.id]
    assert m.match(IP, "2001:db8::/64") == [v6.id]
    assert m.match(IP, "10.0.1.0/24") == []
    assert m.match(IP, "10.0.0.6") == []


def test_exact_literal_values_are_compared_verbatim() -> None:
    m = matcher(entry(AllowlistKind.EXACT, "cmd /c whoami", ObservableType.COMMAND_LINE))
    assert m.is_allowlisted(ObservableType.COMMAND_LINE, "cmd /c whoami")
    assert not m.is_allowlisted(ObservableType.COMMAND_LINE, "cmd /c whoami ")
    assert not m.is_allowlisted(ObservableType.COMMAND_LINE, " cmd /c whoami")

    padded = matcher(entry(AllowlistKind.EXACT, " http://x/ ", URL))
    assert padded.is_allowlisted(URL, " http://x/ ")
    assert not padded.is_allowlisted(URL, "http://x/")


def test_exact_literal_types_are_case_sensitive() -> None:
    m = matcher(
        entry(AllowlistKind.EXACT, "http://example.com/A", URL),
        entry(AllowlistKind.EXACT, "abc123", HASH),
    )
    assert m.is_allowlisted(URL, "http://example.com/A")
    assert not m.is_allowlisted(URL, "http://example.com/a")
    assert not m.is_allowlisted(HASH, "ABC123")


# ── CIDR ─────────────────────────────────────────────────────────────────


def test_cidr_ipv4_boundaries() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "10.0.0.0/8"))
    assert m.is_allowlisted(IP, "10.0.0.0")
    assert m.is_allowlisted(IP, "10.255.255.255")
    assert not m.is_allowlisted(IP, "9.255.255.255")
    assert not m.is_allowlisted(IP, "11.0.0.0")


def test_cidr_ipv6_boundaries() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "2001:db8::/32"))
    assert m.is_allowlisted(IP, "2001:db8::1")
    assert m.is_allowlisted(IP, "2001:0db8:ffff:ffff:ffff:ffff:ffff:ffff")
    assert not m.is_allowlisted(IP, "2001:db9::1")


def test_cidr_versions_do_not_cross() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "0.0.0.0/0"))
    assert m.is_allowlisted(IP, "203.0.113.9")
    assert not m.is_allowlisted(IP, "2001:db8::1")


def test_cidr_only_applies_to_ip_observables() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "10.0.0.0/8"))
    assert not m.is_allowlisted(URL, "10.1.2.3")
    assert not m.is_allowlisted(DOMAIN, "10.1.2.3")
    assert not m.is_allowlisted(URL, "http://10.1.2.3/x")


def test_cidr_suppresses_overlapping_range_indicators() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "10.0.0.0/8"))
    assert m.is_allowlisted(IP, "10.2.0.0/16")  # contained
    assert m.is_allowlisted(IP, "0.0.0.0/4")  # contains the allowlisted range
    assert not m.is_allowlisted(IP, "192.168.0.0/16")


def test_unparseable_ip_observable_never_matches_cidr() -> None:
    m = matcher(entry(AllowlistKind.CIDR, "10.0.0.0/8"))
    assert not m.is_allowlisted(IP, "10.1.2.3:8080")
    assert not m.is_allowlisted(IP, "garbage")


# ── domain suffix ────────────────────────────────────────────────────────


def test_domain_suffix_label_boundaries() -> None:
    m = matcher(entry(AllowlistKind.DOMAIN_SUFFIX, "example.com"))
    assert m.is_allowlisted(DOMAIN, "example.com")
    assert m.is_allowlisted(DOMAIN, "www.example.com")
    assert m.is_allowlisted(DOMAIN, "a.b.Example.COM.")
    assert not m.is_allowlisted(DOMAIN, "badexample.com")
    assert not m.is_allowlisted(DOMAIN, "example.com.evil.net")
    assert not m.is_allowlisted(DOMAIN, "example.co")
    assert not m.is_allowlisted(DOMAIN, "com")


def test_domain_suffix_has_no_implicit_url_or_email_host_matching() -> None:
    m = matcher(entry(AllowlistKind.DOMAIN_SUFFIX, "example.com"))
    assert not m.is_allowlisted(URL, "https://www.example.com/login")
    assert not m.is_allowlisted(EMAIL, "user@example.com")


# ── multiple entries ─────────────────────────────────────────────────────


def test_match_returns_every_matching_entry_id() -> None:
    exact = entry(AllowlistKind.EXACT, "10.1.2.3", IP)
    wide = entry(AllowlistKind.CIDR, "10.0.0.0/8")
    narrow = entry(AllowlistKind.CIDR, "10.1.0.0/16")
    other = entry(AllowlistKind.CIDR, "192.168.0.0/16")
    m = matcher(exact, wide, narrow, other)
    assert set(m.match(IP, "10.1.2.3")) == {exact.id, wide.id, narrow.id}
    assert m.match(IP, "10.9.9.9") == [wide.id]
    assert m.match(IP, "8.8.8.8") == []


def test_empty_matcher_matches_nothing() -> None:
    m = matcher()
    assert m.empty
    assert m.match(IP, "10.1.2.3") == []


# ── exact domain validation (same bare-domain rules as suffixes) ─────────


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "example.com/path",
        "*.example.com",
        "example.com:8443",
        "user@example.com",
        ".example.com",
        "example..com",
        "exa\tmple.com",
        "example.com\n10.0.0.5",
        "1.2.3.4",
        "2001:db8::1",
        ".",
        "a" * 64 + ".com",
    ],
)
def test_exact_domain_rejects_non_bare_domains(value: str) -> None:
    with pytest.raises(AllowlistValidationError):
        canonicalize_entry(AllowlistKind.EXACT, value, DOMAIN)


# ── CIDR index ───────────────────────────────────────────────────────────


def test_cidr_index_returns_every_containing_network() -> None:
    nets = ["0.0.0.0/0", "10.0.0.0/8", "10.1.0.0/16", "10.1.2.0/24", "10.1.2.3/32"]
    entries = {n: entry(AllowlistKind.CIDR, n) for n in nets}
    decoys = [entry(AllowlistKind.CIDR, n) for n in ("10.2.0.0/16", "11.0.0.0/8", "10.1.2.4/32")]
    m = matcher(*entries.values(), *decoys)

    assert set(m.match(IP, "10.1.2.3")) == {e.id for e in entries.values()}
    assert set(m.match(IP, "10.1.2.9")) == {entries[n].id for n in nets[:4]}
    assert set(m.match(IP, "10.200.0.1")) == {entries["0.0.0.0/0"].id, entries["10.0.0.0/8"].id}
    assert m.match(IP, "203.0.113.1") == [entries["0.0.0.0/0"].id]


def test_cidr_index_ipv6_prefix_extremes() -> None:
    everything = entry(AllowlistKind.CIDR, "::/0")
    host = entry(AllowlistKind.CIDR, "2001:db8::1/128")
    mid = entry(AllowlistKind.CIDR, "2001:db8:abcd::/48")
    m = matcher(everything, host, mid)
    assert set(m.match(IP, "2001:db8::1")) == {everything.id, host.id}
    assert set(m.match(IP, "2001:db8:abcd:1::9")) == {everything.id, mid.id}
    assert m.match(IP, "ffff::1") == [everything.id]
    assert m.match(IP, "192.0.2.1") == []  # versions never cross


def test_cidr_index_agrees_with_ipaddress_on_many_networks() -> None:
    import ipaddress
    import random

    rng = random.Random(1234)
    entries = []
    seen: set[str] = set()
    while len(entries) < 400:
        prefix = rng.randint(4, 32)
        net = ipaddress.ip_network((rng.getrandbits(32), prefix), strict=False)
        if str(net) in seen:
            continue
        seen.add(str(net))
        entries.append((net, entry(AllowlistKind.CIDR, str(net))))
    m = matcher(*(e for _, e in entries))

    for _ in range(500):
        addr = ipaddress.ip_address(rng.getrandbits(32))
        expected = {e.id for net, e in entries if addr in net}
        assert set(m.match(IP, str(addr))) == expected


def test_address_lookup_does_not_scan_every_network() -> None:
    entries = [entry(AllowlistKind.CIDR, f"10.{i // 256}.{i % 256}.0/24") for i in range(2000)]
    m = matcher(*entries)
    # One probe per distinct prefix length, however many networks share it.
    assert list(m._network_index[4]) == [24]
    assert m.match(IP, "10.3.5.77") == [entries[3 * 256 + 5].id]
    assert m.match(IP, "10.200.0.1") == []


def test_range_observables_keep_overlap_semantics_with_index() -> None:
    wide = entry(AllowlistKind.CIDR, "10.0.0.0/8")
    narrow = entry(AllowlistKind.CIDR, "10.1.2.0/24")
    exact = entry(AllowlistKind.EXACT, "10.1.2.3", IP)
    m = matcher(wide, narrow, exact)
    assert set(m.match(IP, "10.1.0.0/16")) == {wide.id, narrow.id, exact.id}
    assert set(m.match(IP, "10.9.0.0/16")) == {wide.id}
    assert m.match(IP, "192.0.2.0/24") == []


# ── value size (UTF-8 bytes, not characters) ─────────────────────────────


def test_literal_value_at_byte_limit_is_accepted() -> None:
    ascii_value = "h" * 2048
    assert canonicalize_entry(AllowlistKind.EXACT, ascii_value, URL) == (ascii_value, URL)
    multibyte = "é" * 1024  # 1024 chars, 2048 bytes
    assert canonicalize_entry(AllowlistKind.EXACT, multibyte, URL) == (multibyte, URL)


@pytest.mark.parametrize(
    "value",
    [
        "é" * 1025,  # 1025 chars but 2050 bytes
        "界" * 683,  # 683 chars, 2049 bytes
        "😀" * 2048,  # within the 2048-character cap, 8192 bytes
        "h" * 2049,
    ],
)
def test_literal_value_over_byte_limit_is_rejected(value: str) -> None:
    with pytest.raises(AllowlistValidationError, match="2048 bytes"):
        canonicalize_entry(AllowlistKind.EXACT, value, URL)
