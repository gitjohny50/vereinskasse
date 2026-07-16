"""PIN-Hashing und Token-Erzeugung.

PINs werden niemals im Klartext gespeichert (Lastenheft 6.4). Es wird PBKDF2-
HMAC-SHA256 mit zufälligem Salt und hoher Iterationszahl verwendet - ohne
externe Abhängigkeit, damit der Offline-Betrieb schlank bleibt. Format:

    pbkdf2_sha256$<iterationen>$<salt_hex>$<hash_hex>
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

# Iterationen sind konfigurierbar, damit automatisierte Tests schnell laufen.
# Im Produktivbetrieb bleibt der hohe Standardwert.
_ITERATIONS = int(os.environ.get("VK_PBKDF2_ITERATIONS", "200000"))
_ALGO = "pbkdf2_sha256"


def hash_pin(pin: str) -> str:
    if not pin or not pin.isdigit() or len(pin) < 4:
        raise ValueError("PIN muss mindestens 4 Ziffern haben.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        algo, iterations_s, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    # Zeitkonstanter Vergleich gegen Timing-Angriffe.
    return hmac.compare_digest(digest, expected)


def new_token() -> str:
    return secrets.token_urlsafe(32)
