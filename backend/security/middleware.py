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

    Interactive user/browser requests with authenticated sessions use session auth,
    CSRF, RBAC, and optional replay nonce/timestamp headers for mutating routes.
    API-key signing with nonce/timestamp replay protection applies to unauthenticated
    mutating requests on configured prefixes (default: /api/), except explicit
    allowlisted auth endpoints.
    """

    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    @staticmethod
    def _reject(detail, code, status=401):
        return JsonResponse({"detail": detail, "code": code}, status=status)

    def __init__(self, get_response):
        self.get_response = get_response
        prefixes = getattr(settings, "REQUEST_SIGNING_PREFIXES", ("/api/",))
        self.signed_prefixes = tuple(prefixes)
        allowlist = getattr(
            settings,
            "REQUEST_SIGNING_ALLOWLIST_PATHS",
            (
                "/api/auth/login/",
                "/api/auth/register/",
                "/api/auth/captcha/challenge/",
            ),
        )
        self.allowlist_paths = tuple(allowlist)
        self.require_session_replay_headers = getattr(
            settings, "SESSION_REPLAY_REQUIRE_HEADERS", True
        )

    @staticmethod
    def _parse_timestamp_or_reject(timestamp):
        try:
            parsed = timezone.datetime.fromisoformat(timestamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt_timezone.utc)
            return parsed, None
        except ValueError:
            return None, RequestSigningMiddleware._reject(
                "Invalid timestamp format", "invalid_signature_timestamp"
            )

    @staticmethod
    def _purge_old_nonces():
        ReplayNonce.objects.filter(
            created_at__lt=timezone.now() - timedelta(minutes=10)
        ).delete()

    def _enforce_session_replay_controls(self, request):
        timestamp = request.headers.get("X-Request-Timestamp", "").strip()
        nonce = request.headers.get("X-Request-Nonce", "").strip()
        if not self.require_session_replay_headers and not timestamp and not nonce:
            return None
        if not timestamp and not nonce:
            return self._reject(
                "Missing replay headers", "missing_session_replay_headers", status=400
            )
        if bool(timestamp) != bool(nonce):
            return self._reject(
                "Both X-Request-Timestamp and X-Request-Nonce are required for replay-protected session mutations",
                "missing_session_replay_headers",
                status=400,
            )

        parsed_time, error_response = self._parse_timestamp_or_reject(timestamp)
        if error_response is not None:
            return error_response
        if parsed_time is None:
            return self._reject(
                "Invalid timestamp format", "invalid_signature_timestamp"
            )
        request_time = parsed_time

        if abs((timezone.now() - request_time).total_seconds()) > 300:
            return self._reject(
                "Request timestamp expired", "session_request_timestamp_expired"
            )

        session_key = getattr(request.session, "session_key", None)
        replay_scope = f"session:{session_key or request.user.id}"
        if ReplayNonce.objects.filter(key_id=replay_scope, nonce=nonce).exists():
            return self._reject(
                "Replay nonce detected", "replay_nonce_detected", status=409
            )

        ReplayNonce.objects.create(key_id=replay_scope, nonce=nonce)
        self._purge_old_nonces()
        return None

    def __call__(self, request):
        if request.method not in self.mutating_methods:
            return self.get_response(request)
        if request.path.startswith(self.allowlist_paths):
            return self.get_response(request)
        if not request.path.startswith(self.signed_prefixes):
            return self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            replay_error = self._enforce_session_replay_controls(request)
            if replay_error is not None:
                return replay_error
            return self.get_response(request)

        key_id = request.headers.get("X-Key-Id", "")
        timestamp = request.headers.get("X-Sign-Timestamp", "")
        nonce = request.headers.get("X-Sign-Nonce", "")
        signature = request.headers.get("X-Signature", "")
        if not (key_id and timestamp and nonce and signature):
            return self._reject(
                "Missing signature headers", "missing_signature_headers"
            )

        request_time, error_response = self._parse_timestamp_or_reject(timestamp)
        if error_response is not None:
            return error_response
        if request_time is None:
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
        self._purge_old_nonces()

        request.signed_api_key = key
        request.signed_organization_id = key.organization_id
        return self.get_response(request)
