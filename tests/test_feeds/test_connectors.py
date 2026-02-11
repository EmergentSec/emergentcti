import pytest

from cti.schemas.observable import ObservableCreate
from cti.models.observable import ObservableType


class TestObservableValidation:
    """Test observable type-specific validation via the schema."""

    def test_valid_ipv4(self):
        obs = ObservableCreate(type=ObservableType.ip_addr, value="8.8.8.8")
        assert obs.value == "8.8.8.8"

    def test_valid_ipv6(self):
        obs = ObservableCreate(type=ObservableType.ip_addr, value="::1")
        assert obs.value == "::1"

    def test_invalid_ip(self):
        with pytest.raises(ValueError, match="Invalid IP address"):
            ObservableCreate(type=ObservableType.ip_addr, value="999.999.999.999")

    def test_valid_domain(self):
        obs = ObservableCreate(type=ObservableType.domain_name, value="malware.example.com")
        assert obs.value == "malware.example.com"

    def test_invalid_domain(self):
        with pytest.raises(ValueError, match="Invalid domain"):
            ObservableCreate(type=ObservableType.domain_name, value="-invalid-.com")

    def test_valid_md5(self):
        md5 = "d41d8cd98f00b204e9800998ecf8427e"
        obs = ObservableCreate(type=ObservableType.file_hash, value=md5)
        assert obs.value == md5

    def test_valid_sha256(self):
        sha256 = "a" * 64
        obs = ObservableCreate(type=ObservableType.file_hash, value=sha256)
        assert obs.value == sha256

    def test_invalid_hash_length(self):
        with pytest.raises(ValueError, match="Invalid hash length"):
            ObservableCreate(type=ObservableType.file_hash, value="abc123")

    def test_invalid_hash_chars(self):
        with pytest.raises(ValueError, match="hexadecimal"):
            ObservableCreate(type=ObservableType.file_hash, value="g" * 32)

    def test_valid_email(self):
        obs = ObservableCreate(type=ObservableType.email_addr, value="threat@evil.com")
        assert obs.value == "threat@evil.com"

    def test_invalid_email(self):
        with pytest.raises(ValueError, match="Invalid email"):
            ObservableCreate(type=ObservableType.email_addr, value="notanemail")

    def test_valid_cidr(self):
        obs = ObservableCreate(type=ObservableType.cidr, value="192.168.0.0/24")
        assert obs.value == "192.168.0.0/24"

    def test_invalid_cidr(self):
        with pytest.raises(ValueError, match="Invalid CIDR"):
            ObservableCreate(type=ObservableType.cidr, value="not/a/cidr")

    def test_valid_asn(self):
        obs = ObservableCreate(type=ObservableType.asn, value="AS15169")
        assert obs.value == "AS15169"

    def test_invalid_asn(self):
        with pytest.raises(ValueError, match="Invalid ASN"):
            ObservableCreate(type=ObservableType.asn, value="15169")

    def test_valid_url(self):
        obs = ObservableCreate(type=ObservableType.url, value="https://evil.com/malware.exe")
        assert obs.value == "https://evil.com/malware.exe"

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Invalid URL"):
            ObservableCreate(type=ObservableType.url, value="not a url")

    def test_confidence_range(self):
        with pytest.raises(ValueError):
            ObservableCreate(type=ObservableType.ip_addr, value="1.2.3.4", confidence_score=101)

        with pytest.raises(ValueError):
            ObservableCreate(type=ObservableType.ip_addr, value="1.2.3.4", confidence_score=-1)

    def test_hash_lowercased(self):
        sha256 = "A" * 64
        obs = ObservableCreate(type=ObservableType.file_hash, value=sha256)
        assert obs.value == "a" * 64
