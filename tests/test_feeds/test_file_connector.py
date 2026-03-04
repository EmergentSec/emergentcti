"""Test file connector parsing logic."""

from cti.feeds.file_connector import FileFeedConnector
from cti.models.observable import ObservableType


def test_normalize_text_lines() -> None:
    """Test parsing plain text IP list."""
    connector = FileFeedConnector(
        url="https://example.com/ips.txt",
        config={"format": "text", "default_type": "ip-addr", "comment_char": "#"},
    )

    raw_data = "# This is a comment\n1.2.3.4\n5.6.7.8\n\n# Another comment\n9.10.11.12\n"
    observables = connector.normalize(raw_data)

    assert len(observables) == 3
    assert observables[0].value == "1.2.3.4"
    assert observables[0].type == ObservableType.IP_ADDR
    assert observables[1].value == "5.6.7.8"
    assert observables[2].value == "9.10.11.12"


def test_normalize_skips_empty_and_comments() -> None:
    connector = FileFeedConnector(
        url="https://example.com/list.txt",
        config={"format": "text", "default_type": "url", "comment_char": "#"},
    )

    raw_data = "# header\n\n  \nhttps://evil.com\n# footer\n"
    observables = connector.normalize(raw_data)

    assert len(observables) == 1
    assert observables[0].value == "https://evil.com"
    assert observables[0].type == ObservableType.URL
