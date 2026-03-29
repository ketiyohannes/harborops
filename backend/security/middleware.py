import hashlib
import hmac
from datetime import timezone as dt_timezone
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from core.crypto import decrypt_text
from security.models import ApiClientKey, ReplayNonce


class RequestSigningMiddleware:
    """Enforce HMAC signing for configured machine mutation routes.

    Interactive user/browser requests with authenticated sessions are protected by
    session auth, CSRF, and RBAC and are not forced through API-key signing.
    API-key signing with nonce/timestamp replay protection applies to configured
    mutating route prefixes (default: /api/jobs/).
    """

    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    @staticmethod
    def _reject(detail, code, status=401):
        return JsonResponse({"detail": detail, "code": code}, status=status)

    def __init__(self, get_response):
        self.get_response = get_response
        prefixes = getattr(settings, "REQUEST_SIGNING_PREFIXES", ("/api/jobs/worker/",))
        self.signed_prefixes = tuple(prefixes)

    def __call__(self, request):
        if request.method not in self.mutating_methods:
            return self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            return self.get_response(request)
        if not request.path.startswith(self.signed_prefixes):
            return self.get_response(request)

        key_id = request.headers.get("X-Key-Id", "")
        timestamp = request.headers.get("X-Sign-Timestamp", "")
        nonce = request.headers.get("X-Sign-Nonce", "")
        signature = request.headers.get("X-Signature", "")
        if not (key_id and timestamp and nonce and signature):
            return self._reject(
                "Missing signature headers", "missing_signature_headers"
            )

        try:
            request_time = timezone.datetime.fromisoformat(timestamp)
            if request_time.tzinfo is None:
                request_time = request_time.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            return self._reject(
                "Invalid timestamp format", "invalid_signature_timestamp"
            )

        if abs((timezone.now() - request_time).total_seconds()) > 300:
            return self._reject(
                "Signature timestamp expired", "signature_timestamp_expired"
            )

        try:
            key = ApiClientKey.objects.get(
                key_id=key_id, is_active=True, revoked_at__isnull=True
            )
        except ApiClientKey.DoesNotExist:
            return self._reject("Invalid key_id", "invalid_signature_key")

        if ReplayNonce.objects.filter(key_id=key_id, nonce=nonce).exists():
            return self._reject("Replay nonce detected", "replay_nonce_detected")

        body = request.body.decode("utf-8") if request.body else ""
        payload = "\n".join([request.method, request.path, timestamp, nonce, body])
        if not key.secret_encrypted:
            return self._reject(
                "Signing key material unavailable", "signing_key_material_unavailable"
            )

        secret = decrypt_text(key.secret_encrypted)
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return self._reject("Invalid signature", "invalid_signature")

        ReplayNonce.objects.create(key_id=key_id, nonce=nonce)
        ReplayNonce.objects.filter(
            created_at__lt=timezone.now() - timedelta(minutes=10)
        ).delete()

        request.signed_api_key = key
        request.signed_organization_id = key.organization_id
        return self.get_response(request)
