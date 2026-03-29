import base64
import os

from django.core.exceptions import ImproperlyConfigured

INSECURE_DEFAULT_AES_KEYS = {
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}

INSECURE_PLACEHOLDER_AES_KEYS = {
    "change-me",
    "replace-me",
    "replace-with-generated-key",
    "replace-with-unique-key",
}


def validate_app_aes_key_environment():
    key_b64 = os.getenv("APP_AES256_KEY_B64", "").strip()
    if not key_b64:
        raise ImproperlyConfigured(
            "APP_AES256_KEY_B64 is required and must be a unique base64-encoded 32-byte key."
        )
    if key_b64 in INSECURE_DEFAULT_AES_KEYS:
        raise ImproperlyConfigured(
            "APP_AES256_KEY_B64 uses an insecure default value; configure a unique key."
        )
    if key_b64.lower() in INSECURE_PLACEHOLDER_AES_KEYS:
        raise ImproperlyConfigured(
            "APP_AES256_KEY_B64 uses a placeholder value; configure a unique key."
        )
    try:
        decoded = base64.b64decode(key_b64, validate=True)
    except Exception as exc:  # pragma: no cover - exact exception varies by runtime
        raise ImproperlyConfigured(
            "APP_AES256_KEY_B64 must be valid base64 and decode to 32 bytes."
        ) from exc
    if len(decoded) != 32:
        raise ImproperlyConfigured(
            "APP_AES256_KEY_B64 must decode to exactly 32 bytes."
        )
    return True
