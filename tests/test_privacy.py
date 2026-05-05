import pytest

from nimbus.privacy.hashing import hash_mac
from nimbus.privacy.optout import is_opted_out


class TestHashMac:
    def test_same_mac_same_salt_produces_same_hash(self, salt: bytes) -> None:
        assert hash_mac("AA:BB:CC:DD:EE:FF", salt) == hash_mac("AA:BB:CC:DD:EE:FF", salt)

    def test_different_salt_produces_different_hash(self, salt: bytes) -> None:
        other_salt = b"different-salt-fixed-32-bytes-!!"
        assert hash_mac("AA:BB:CC:DD:EE:FF", salt) != hash_mac("AA:BB:CC:DD:EE:FF", other_salt)

    def test_normalizes_separators(self, salt: bytes) -> None:
        assert hash_mac("aa:bb:cc:dd:ee:ff", salt) == hash_mac("AA-BB-CC-DD-EE-FF", salt)

    def test_output_is_16_hex_chars(self, salt: bytes) -> None:
        result = hash_mac("AA:BB:CC:DD:EE:FF", salt)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_raw_mac_never_in_output(self, salt: bytes) -> None:
        result = hash_mac("AA:BB:CC:DD:EE:FF", salt)
        assert "aa:bb:cc:dd:ee:ff" not in result


class TestOptOut:
    def test_exact_match(self) -> None:
        assert is_opted_out("AA:BB:CC:DD:EE:FF", ["aa:bb:cc:dd:ee:ff"])

    def test_prefix_match(self) -> None:
        assert is_opted_out("AA:BB:CC:11:22:33", ["aa:bb:cc"])

    def test_no_match(self) -> None:
        assert not is_opted_out("AA:BB:CC:DD:EE:FF", ["11:22:33"])

    def test_empty_list(self) -> None:
        assert not is_opted_out("AA:BB:CC:DD:EE:FF", [])
