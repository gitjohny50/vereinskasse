import pytest

from app import security


def test_hash_is_not_plaintext():
    h = security.hash_pin("1234")
    assert "1234" not in h
    assert h.startswith("pbkdf2_sha256$")


def test_verify_correct_and_wrong():
    h = security.hash_pin("4711")
    assert security.verify_pin("4711", h) is True
    assert security.verify_pin("4712", h) is False


def test_hashes_are_salted_unique():
    assert security.hash_pin("1234") != security.hash_pin("1234")


def test_short_pin_rejected():
    with pytest.raises(ValueError):
        security.hash_pin("12")


def test_malformed_stored_hash_returns_false():
    assert security.verify_pin("1234", "kaputt") is False


def test_tokens_unique():
    assert security.new_token() != security.new_token()
