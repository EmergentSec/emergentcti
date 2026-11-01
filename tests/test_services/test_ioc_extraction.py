"""Deterministic IOC extraction rules (issue #14 contract)."""

from __future__ import annotations

import time

import pytest

from cti.models.observable import ObservableType
from cti.services import ioc_extraction
from cti.services.ioc_extraction import Candidate, extract

IP = ObservableType.IP_ADDR
DOMAIN = ObservableType.DOMAIN_NAME
URL = ObservableType.URL
HASH = ObservableType.FILE_HASH
EMAIL = ObservableType.EMAIL_ADDR

MD5 = "d41d8cd98f00b204e9800998ecf8427e"
SHA1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def by_key(text: str) -> dict[tuple[ObservableType, str], Candidate]:
    return {(c.type, c.value): c for c in extract([text]).candidates}


def keys(text: str) -> set[tuple[ObservableType, str]]:
    return set(by_key(text))


def test_each_supported_type_is_extracted_and_normalized() -> None:
    text = (
        f"IP 185.220.101.42 and 2001:4860:4860::8888, domain Evil-Domain.Example., "
        f"url HTTPS://C2.Example/Path?Q=A#Frag, mail Ops.Team@Corp.Example, "
        f"hashes {MD5.upper()} {SHA1} {SHA256}"
    )
    found = by_key(text)
    assert set(found) == {
        (IP, "185.220.101.42"),
        (IP, "2001:4860:4860::8888"),
        (DOMAIN, "evil-domain.example"),
        (URL, "https://c2.example/Path?Q=A#Frag"),
        (EMAIL, "Ops.Team@corp.example"),
        (HASH, MD5),
        (HASH, SHA1),
        (HASH, SHA256),
    }
    assert all(candidate.valid for candidate in found.values())
    assert found[(HASH, MD5)].warnings == ["hash_md5"]
    assert found[(HASH, SHA1)].warnings == ["hash_sha1"]
    assert found[(HASH, SHA256)].warnings == []
    assert found[(HASH, MD5)].original == MD5.upper()
    assert found[(IP, "185.220.101.42")].warnings == []


def test_command_line_is_never_extracted() -> None:
    candidates = extract(["powershell.exe -enc AAAA && cmd /c whoami"]).candidates
    assert all(c.type is not ObservableType.COMMAND_LINE for c in candidates)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("evil[.]example", (DOMAIN, "evil.example")),
        ("evil(.)example", (DOMAIN, "evil.example")),
        ("evil{.}example", (DOMAIN, "evil.example")),
        ("evil[dot]example", (DOMAIN, "evil.example")),
        ("evil(dot)example", (DOMAIN, "evil.example")),
        ("evil{dot}example", (DOMAIN, "evil.example")),
        ("evil[DOT]example", (DOMAIN, "evil.example")),
        ("evil dot example", (DOMAIN, "evil.example")),
        ("185[.]220[.]101[.]42", (IP, "185.220.101.42")),
        ("hxxp://evil.example/a", (URL, "http://evil.example/a")),
        ("hXXp://evil.example/a", (URL, "http://evil.example/a")),
        ("hxxps://evil.example/a", (URL, "https://evil.example/a")),
        ("hXXps://evil.example/a", (URL, "https://evil.example/a")),
        ("http[:]//evil.example/a", (URL, "http://evil.example/a")),
        ("http[://]evil.example/a", (URL, "http://evil.example/a")),
        ("hxxps[://]evil[.]example/a", (URL, "https://evil.example/a")),
        ("hxxp[:]//evil[.]example:8080/a", (URL, "http://evil.example:8080/a")),
        ("user[@]evil.example", (EMAIL, "user@evil.example")),
        ("user[at]evil[.]example", (EMAIL, "user@evil.example")),
        ("user(at)evil.example", (EMAIL, "user@evil.example")),
    ],
)
def test_every_defang_form_is_refanged(
    written: str,
    expected: tuple[ObservableType, str],
) -> None:
    found = by_key(f"Indicator: {written} seen.")
    assert expected in found, found
    candidate = found[expected]
    assert candidate.defanged is True
    assert candidate.original == written
    assert candidate.valid is True


def test_plain_tokens_are_not_marked_defanged() -> None:
    found = by_key("Seen evil.example and http://evil.example/x")
    assert found[(DOMAIN, "evil.example")].defanged is False
    assert found[(URL, "http://evil.example/x")].defanged is False


@pytest.mark.parametrize("token", ["999.1.1.1", "256.10.10.10", "10.010.1.1"])
def test_invalid_ipv4_is_reported_invalid(token: str) -> None:
    candidate = by_key(f"Bad address {token} here")[(IP, token)]
    assert candidate.valid is False
    assert candidate.warnings == ["invalid_ip"]


def test_repeated_character_hash_is_invalid() -> None:
    zeros = "0" * 64
    found = by_key(f"sha256 {zeros} and md5 {'a' * 32}")
    assert found[(HASH, zeros)].valid is False
    assert found[(HASH, zeros)].warnings == ["invalid_hash"]
    assert found[(HASH, "a" * 32)].valid is False


def test_hash_lengths_other_than_32_40_64_are_ignored() -> None:
    assert keys(f"{'ab' * 17} {'cd' * 24} {MD5}x{MD5}") == {(HASH, MD5)}
    # Bounded by hex on one side: not a hash.
    assert keys(f"{MD5}abc") == set()


@pytest.mark.parametrize(
    "address",
    ["10.0.0.1", "192.168.1.1", "127.0.0.1", "169.254.1.1", "224.0.0.1", "0.0.0.0", "::1"],
)
def test_non_public_ips_are_valid_with_warning(address: str) -> None:
    candidate = by_key(f"addr {address} end")[(IP, address)]
    assert candidate.valid is True
    assert candidate.warnings == ["non_public_ip"]


def test_ipv6_canonical_form_and_noise_rejected() -> None:
    found = keys("v6 2001:DB8:0:0:0:0:0:1 at 12:30:45 using std::vector and a::b")
    assert found == {(IP, "2001:db8::1")}


def test_filename_like_tokens_suppressed_unless_defanged() -> None:
    found = by_key("Open invoice.pdf, run payload.exe, see Node.js; dropper loader[.]exe")
    assert (DOMAIN, "invoice.pdf") not in found
    assert (DOMAIN, "payload.exe") not in found
    assert (DOMAIN, "node.js") not in found
    defanged = found[(DOMAIN, "loader.exe")]
    assert defanged.valid is True
    assert defanged.defanged is True
    assert defanged.warnings == ["looks_like_filename"]


def test_non_domain_shapes_are_ignored() -> None:
    assert keys("e.g. i.e. v1.2 Fig.3 1.2.3 and_under.score.example") == set()


def test_invalid_domain_label_is_reported_invalid() -> None:
    long_label = "x" * 64  # non-hex, so the hash phase does not claim it
    found = by_key(f"host {long_label}.example and -bad.example")
    assert found[(DOMAIN, f"{long_label}.example")].warnings == ["invalid_domain"]
    assert found[(DOMAIN, f"{long_label}.example")].valid is False
    assert found[(DOMAIN, "-bad.example")].valid is False


def test_url_host_is_not_double_emitted() -> None:
    found = keys("Beacon http://c2.example/gate.php and https://198.51.100.7:443/x")
    assert found == {
        (URL, "http://c2.example/gate.php"),
        (URL, "https://198.51.100.7:443/x"),
    }


def test_url_trailing_punctuation_is_stripped_and_path_kept() -> None:
    found = keys('See (https://evil.example/A/B?x=1). Also "http://other.example/Q",')
    assert found == {
        (URL, "https://evil.example/A/B?x=1"),
        (URL, "http://other.example/Q"),
    }


def test_markdown_link_yields_both_urls() -> None:
    found = keys("[http://a.example](http://a.example/x) <https://b.example>")
    assert found == {
        (URL, "http://a.example"),
        (URL, "http://a.example/x"),
        (URL, "https://b.example"),
    }


def test_url_with_invalid_host_is_not_emitted() -> None:
    found = by_key("Local http://localhost/admin and http://999.2.2.2/x ftp://bad_host.example/")
    assert not any(key[0] is URL for key in found)
    # The dotted quad is still reported on its own, as invalid.
    assert found[(IP, "999.2.2.2")].valid is False


def test_unsupported_scheme_is_not_a_url() -> None:
    found = keys("javascript://evil.example/x and sftp://files.example/drop")
    assert (URL, "sftp://files.example/drop") in found
    assert not any(key[0] is URL and key[1].startswith("javascript") for key in found)


def test_url_values_never_carry_invisible_characters() -> None:
    # Format characters are removed before matching, never kept in a value.
    found = by_key("http://evil.example/a‮gnp.exe")
    assert set(found) == {(URL, "http://evil.example/agnp.exe")}
    assert found[(URL, "http://evil.example/agnp.exe")].original == "http://evil.example/agnp.exe"


FORMAT_CHARS = [
    "\u00ad",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2064",
    "\ufeff",
]


@pytest.mark.parametrize("char", FORMAT_CHARS)
def test_format_characters_inside_a_domain_are_removed(char: str) -> None:
    found = by_key(f"see evil{char}exa{char}mple.com now")
    assert set(found) == {(DOMAIN, "evilexample.com")}
    assert found[(DOMAIN, "evilexample.com")].original == "evilexample.com"
    assert char not in found[(DOMAIN, "evilexample.com")].context


@pytest.mark.parametrize("char", FORMAT_CHARS)
def test_format_characters_inside_a_url_are_removed(char: str) -> None:
    assert keys(f"get http{char}s://c2.ex{char}ample/ga{char}te ok") == {
        (URL, "https://c2.example/gate")
    }


@pytest.mark.parametrize("char", FORMAT_CHARS)
def test_format_characters_around_email_at_sign_are_removed(char: str) -> None:
    found = by_key(f"mail user{char}@{char}pay{char}-portal.example today")
    assert set(found) == {(EMAIL, "user@pay-portal.example")}
    assert found[(EMAIL, "user@pay-portal.example")].original == "user@pay-portal.example"


@pytest.mark.parametrize("char", FORMAT_CHARS)
def test_format_characters_inside_defang_markers_are_removed(char: str) -> None:
    found = by_key(f"evil[{char}.]example")
    assert set(found) == {(DOMAIN, "evil.example")}
    assert found[(DOMAIN, "evil.example")].defanged is True


def test_review_reproducers_for_format_characters() -> None:
    # The reviewer's literal inputs ("\u202examp" is U+202E then "xamp").
    assert keys("evil\u202examp\u200cle.com") == {(DOMAIN, "evilxample.com")}
    assert keys("evil\u202eexamp\u200cle.com") == {(DOMAIN, "evilexample.com")}
    assert keys("user\u200c@pay-portal.example") == {(EMAIL, "user@pay-portal.example")}
    assert keys("mail user\u202e@pay\u200c-portal.example") == {(EMAIL, "user@pay-portal.example")}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("visit münchen.example today", (DOMAIN, "xn--mnchen-3ya.example")),
        ("visit MÜNCHEN.Example today", (DOMAIN, "xn--mnchen-3ya.example")),
        ("host evil.exampleü here", (DOMAIN, "evil.xn--example-t2a")),
        ("host shop.bücher.example here", (DOMAIN, "shop.xn--bcher-kva.example")),
        ("host 例え.jp here", (DOMAIN, "xn--r8jz45g.jp")),
        ("defanged münchen[.]example", (DOMAIN, "xn--mnchen-3ya.example")),
        ("url https://münchen.example/p?q=ü", (URL, "https://xn--mnchen-3ya.example/p?q=ü")),
        (
            "url http://user@bücher.example:8080/x",
            (URL, "http://user@xn--bcher-kva.example:8080/x"),
        ),
        ("mail ops@bücher.example now", (EMAIL, "ops@xn--bcher-kva.example")),
        ("mail ops@münchen.example.", (EMAIL, "ops@xn--mnchen-3ya.example")),
    ],
)
def test_non_ascii_host_labels_are_taken_whole_and_idna_encoded(
    text: str, expected: tuple[ObservableType, str]
) -> None:
    found = by_key(text)
    assert set(found) == {expected}
    assert found[expected].valid is True


@pytest.mark.parametrize(
    ("text", "suffix"),
    [
        ("visit münchen.example", "nchen.example"),
        ("see zürich.example", "rich.example"),
        ("https://münchen.example/x", "nchen.example"),
        ("ops@bücher.example", "cher.example"),
    ],
)
def test_no_candidate_is_a_suffix_of_a_non_ascii_host(text: str, suffix: str) -> None:
    candidates = extract([text]).candidates
    assert len(candidates) == 1
    assert candidates[0].value.isascii()
    assert "xn--" in candidates[0].value
    assert suffix not in candidates[0].value


@pytest.mark.parametrize(
    "text",
    [
        "x" + "ü" * 70 + ".example",  # Label longer than 63: does not encode.
        "ü" * 250 + ".example",  # Host longer than 253.
        "mail ops@" + "ü" * 70 + ".example",
        "https://" + "ü" * 70 + ".example/x",
    ],
)
def test_non_ascii_host_that_does_not_encode_emits_nothing(text: str) -> None:
    assert extract([text]).candidates == []


def test_email_domain_is_not_double_emitted() -> None:
    assert keys("Phish from billing@pay-portal.example today") == {
        (EMAIL, "billing@pay-portal.example")
    }


@pytest.mark.parametrize(
    "text", ["contact jürgen@firma.de now", "üser@firma.de", "x 用户@firma.de"]
)
def test_email_local_part_is_never_truncated_at_non_ascii(text: str) -> None:
    emitted = keys(text)
    assert not any(kind == EMAIL for kind, _ in emitted)
    assert (DOMAIN, "firma.de") in emitted


def test_dedup_counts_occurrences_and_keeps_first_original() -> None:
    text = "First evil[.]example then EVIL.example then evil.example."
    candidate = by_key(text)[(DOMAIN, "evil.example")]
    assert candidate.occurrences == 3
    assert candidate.original == "evil[.]example"
    assert candidate.defanged is True


def test_first_occurrence_across_sources_supplies_context() -> None:
    result = extract(["content mentions 185.220.101.42 first", "attachment 185.220.101.42"])
    (candidate,) = result.candidates
    assert candidate.occurrences == 2
    assert candidate.context == "content mentions 185.220.101.42 first"


def test_context_is_plain_collapsed_and_capped() -> None:
    padding = "word " * 40
    text = f"{padding}\n\n\tsee​  evil.example\r\n now {padding}"
    candidate = by_key(text)[(DOMAIN, "evil.example")]
    assert "\n" not in candidate.context
    assert "​" not in candidate.context
    assert "  " not in candidate.context
    assert "see evil.example now" in candidate.context
    assert len(candidate.context) <= ioc_extraction.CONTEXT_MAX_LENGTH


def test_candidates_sorted_by_type_then_value() -> None:
    result = extract([f"z.example a.example 8.8.8.8 1.1.1.1 {MD5} http://b.example/"])
    order = [(c.type.value, c.value) for c in result.candidates]
    assert order == sorted(order)


def test_character_limit_sets_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ioc_extraction, "MAX_SCAN_CHARS", 30)
    result = extract(["early.example " + "x" * 20 + " late.example", "other.example"])
    assert result.truncated is True
    assert {c.value for c in result.candidates} == {"early.example"}


def test_candidate_limit_keeps_earliest_and_sets_truncated() -> None:
    text = " ".join(f"host{i}.example" for i in range(ioc_extraction.MAX_CANDIDATES + 5))
    result = extract([text])
    assert result.truncated is True
    assert len(result.candidates) == ioc_extraction.MAX_CANDIDATES
    values = {c.value for c in result.candidates}
    assert "host0.example" in values
    assert f"host{ioc_extraction.MAX_CANDIDATES + 4}.example" not in values


def test_not_truncated_for_small_input() -> None:
    assert extract(["evil.example"]).truncated is False
    assert extract([]).candidates == []


def test_overlong_url_is_invalid_and_clipped() -> None:
    url = "http://evil.example/" + "a" * 3000
    candidate = by_key(url)[(URL, url[: ioc_extraction.MAX_VALUE_LENGTH])]
    assert candidate.valid is False
    assert candidate.warnings == ["value_too_long"]


@pytest.mark.parametrize(
    "text",
    [
        "a" * 2_000_000,
        "a." * 1_000_000,
        "1:" * 1_000_000,
        "a@" * 1_000_000,
        "http://" + "a" * 1_999_000,
        "0" * 2_000_000,
        "[.]" * 600_000,
        "1.1." * 500_000,
        "ü." * 1_000_000,
        "ü" * 1_999_000 + ".example",
        "a@" + "ü" * 1_999_000,
        "\u200b" * 2_000_000,
        "ü\u200b." * 600_000,
        "http://" + "ü" * 1_999_000,
        " ".join(f"x{i}.ü" for i in range(260_000))[:2_000_000],  # Distinct IDNA hosts.
    ],
)
def test_pathological_input_runs_in_linear_time(text: str) -> None:
    started = time.perf_counter()
    extract([text])
    # Quadratic behaviour on 2M chars would take minutes; leave headroom for
    # loaded CI workers while keeping a meaningful upper bound.
    assert time.perf_counter() - started < 30


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("evil\uff0eexample.com", (DOMAIN, "evil.example.com")),
        ("evil\u3002example.com", (DOMAIN, "evil.example.com")),
        ("sub\uff61domain.example.com", (DOMAIN, "sub.domain.example.com")),
        ("évil.example", (DOMAIN, "xn--vil-9la.example")),
        ("évil.example", (DOMAIN, "xn--vil-9la.example")),
    ],
)
def test_dot_homoglyphs_and_combining_marks_never_yield_suffix_hosts(
    text: str, expected: tuple[ObservableType, str]
) -> None:
    assert keys(text) == {expected}


@pytest.mark.parametrize(
    "text",
    [
        "ex\u0301ample.com",  # x + acute has no precomposed form
        "e\u0301\u0302vil.example",  # stacked marks: NFC composes only the first
        "evil.ex\u0331ample.com",
        "user@x\u0301y.example",
        "q\u0301@pay.example",
    ],
)
def test_uncomposable_combining_marks_never_yield_suffix_hosts(text: str) -> None:
    suffixes = {"ample.com", "vil.example", "evil.ex", "y.example"}
    emitted = keys(text)
    assert emitted, "the whole host must still be emitted"
    assert not any(value in suffixes for _, value in emitted)
    for _, value in emitted:
        assert value.isascii()  # whole host IDNA-encoded, never a raw fragment
    if text.startswith("q"):
        # Local part starts after a mark: no truncated email, whole host kept.
        assert emitted == {(DOMAIN, "pay.example")}


def test_scan_budget_applies_after_nfc_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    # U+1D1C0 expands to three code points under NFC.
    monkeypatch.setattr(ioc_extraction, "MAX_SCAN_CHARS", 30)
    result = extract(["\U0001d1c0" * 20 + " evil.example"])
    # Pre-fix, 30 raw chars normalized to 70 and " evil.exam" was scanned.
    assert result.truncated is True
    assert result.candidates == []
