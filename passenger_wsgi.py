import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import time
from datetime import datetime
from http.cookies import SimpleCookie
from threading import Lock
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from getpass import getpass

from vercyra_network_security import VercyraBusinessSecurity
from vercyra_security_api import (
    TIERS,
    billing_snapshot,
    dashboard_snapshot,
    get_paypal_access_token,
    has_feature,
    paypal_request,
    process_verified_webhook,
)


SESSION_COOKIE = "vercyra_dashboard_session"
SESSION_MAX_AGE = 8 * 60 * 60
LOGIN_FAILURE_LIMIT = 8
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCK_SECONDS = 15 * 60
LOGIN_TRACKED_CLIENT_LIMIT = 5_000
_login_failures = {}
_login_failures_lock = Lock()
_login_failures_last_pruned = 0.0
monitor = VercyraBusinessSecurity()


def create_password_hash(password, salt=None, iterations=310_000):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password, encoded_hash):
    try:
        algorithm, iterations_text, salt, expected = encoded_hash.split("$", 3)
        iterations = int(iterations_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (AttributeError, TypeError, ValueError):
        return False


def _session_secret():
    return os.getenv("VERCYRA_SESSION_SECRET", "")


def _new_session_token():
    issued = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    message = f"{issued}.{nonce}".encode("ascii")
    signature = hmac.new(_session_secret().encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{issued}.{nonce}.{signature}"


def _authenticated(environ):
    secret = _session_secret()
    if not secret:
        return False
    cookies = SimpleCookie()
    try:
        cookies.load(environ.get("HTTP_COOKIE", ""))
        token = cookies[SESSION_COOKIE].value
        issued_text, nonce, signature = token.split(".", 2)
        issued = int(issued_text)
    except (KeyError, ValueError, TypeError):
        return False
    now = int(time.time())
    if issued > now or now - issued > SESSION_MAX_AGE:
        return False
    message = f"{issued_text}.{nonce}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _origin_allowed(environ):
    origin = environ.get("HTTP_ORIGIN", "")
    configured_origins = [os.getenv("VERCYRA_PUBLIC_URL", "")]
    configured_origins.extend(os.getenv("VERCYRA_ALLOWED_ORIGINS", "").split(","))
    allowed = set()
    for configured_origin in configured_origins:
        configured = urlparse(configured_origin.strip())
        if configured.scheme in {"http", "https"} and configured.netloc and not configured.username:
            allowed.add(f"{configured.scheme.lower()}://{configured.netloc.lower()}")
    return origin.lower() in allowed


def _login_client_key(environ):
    # Railway's private backend is reached through the frontend Caddy proxy.
    # Keep the backend private so this forwarded address comes from that proxy.
    forwarded_for = environ.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() or environ.get("REMOTE_ADDR", "unknown")
    return client_ip[:128]


def _prune_login_failures(now):
    global _login_failures_last_pruned
    if now - _login_failures_last_pruned < 60:
        return
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    for client_ip, (failures, locked_until) in list(_login_failures.items()):
        failures = [timestamp for timestamp in failures if timestamp > cutoff]
        if failures or locked_until > now:
            _login_failures[client_ip] = (failures, locked_until)
        else:
            _login_failures.pop(client_ip, None)
    _login_failures_last_pruned = now


def _login_retry_after(client_ip):
    now = time.monotonic()
    with _login_failures_lock:
        _prune_login_failures(now)
        failures, locked_until = _login_failures.get(client_ip, ([], 0.0))
        if locked_until > now:
            return max(1, int(locked_until - now + 0.999))
    return 0


def _record_failed_login(client_ip):
    now = time.monotonic()
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    with _login_failures_lock:
        _prune_login_failures(now)
        failures, locked_until = _login_failures.get(client_ip, ([], 0.0))
        failures = [timestamp for timestamp in failures if timestamp > cutoff]
        failures.append(now)
        if len(failures) >= LOGIN_FAILURE_LIMIT:
            locked_until = now + LOGIN_LOCK_SECONDS
        if client_ip not in _login_failures and len(_login_failures) >= LOGIN_TRACKED_CLIENT_LIMIT:
            _login_failures.pop(next(iter(_login_failures)))
        _login_failures[client_ip] = (failures, locked_until)


def _clear_login_failures(client_ip):
    with _login_failures_lock:
        _login_failures.pop(client_ip, None)


def _json_response(start_response, status, payload, extra_headers=()):
    body = json.dumps(payload).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        *extra_headers,
    ]
    start_response(f"{status} {_reason(status)}", headers)
    return [body]


def _reason(status):
    return {
        200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
        404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large",
        429: "Too Many Requests",
        422: "Unprocessable Entity", 500: "Internal Server Error", 501: "Not Implemented",
        503: "Service Unavailable",
    }.get(status, "Error")


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError as error:
        raise ValueError("Invalid Content-Length") from error
    if length < 0 or length > 256_000:
        raise OverflowError("Request body is too large")
    try:
        return json.loads(environ["wsgi.input"].read(length) or b"{}")
    except json.JSONDecodeError as error:
        raise ValueError("Invalid JSON body") from error


def _paypal_subscribe(tier):
    plan_config = TIERS[tier]
    plan_id = os.getenv(plan_config["plan_env"], "")
    if not plan_id or plan_id.startswith("replace-"):
        raise ValueError("PayPal plan IDs are not configured")

    public_url = urlparse(os.getenv("VERCYRA_PUBLIC_URL", ""))
    webhook_url = urlparse(os.getenv("PAYPAL_WEBHOOK_URL", ""))
    if (
        os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower() == "live"
        and (
            public_url.scheme != "https"
            or not public_url.netloc
            or "replace-" in public_url.netloc
            or webhook_url.scheme != "https"
            or not webhook_url.netloc
            or "replace-" in webhook_url.netloc
        )
    ):
        raise ValueError("Live checkout requires public HTTPS return and webhook URLs")

    base_url = os.getenv("VERCYRA_PUBLIC_URL", "").rstrip("/")
    if not base_url:
        raise ValueError("VERCYRA_PUBLIC_URL is not configured")
    token = get_paypal_access_token()
    response = paypal_request(
        "/v1/billing/subscriptions",
        {
            "plan_id": plan_id,
            "application_context": {
                "brand_name": "Vercyra Security",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": f"{base_url}/?billing=return",
                "cancel_url": f"{base_url}/?billing=cancel",
            },
        },
        access_token=token,
    )
    approval_url = next(
        (link["href"] for link in response.get("links", []) if link.get("rel") == "approve"),
        None,
    )
    if not approval_url:
        raise RuntimeError("PayPal did not return an approval URL")
    return {"approval_url": approval_url, "subscription_id": response.get("id")}


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    if path.startswith("/api/"):
        path = path[4:]
    elif path == "/api":
        path = "/"

    if method == "GET" and path == "/health":
        return _json_response(start_response, 200, {"status": "ok"})

    if method == "GET" and path == "/auth/session":
        return _json_response(
            start_response,
            200,
            {
                "authenticated": _authenticated(environ),
                "ready": bool(os.getenv("VERCYRA_DASHBOARD_PASSWORD_HASH") and _session_secret()),
            },
        )

    if method == "POST" and path == "/auth/login":
        password_hash = os.getenv("VERCYRA_DASHBOARD_PASSWORD_HASH", "")
        if not password_hash or not _session_secret():
            return _json_response(start_response, 503, {"error": "Dashboard authentication is not configured"})
        if not _origin_allowed(environ):
            return _json_response(start_response, 403, {"error": "Request origin is not allowed"})
        client_ip = _login_client_key(environ)
        retry_after = _login_retry_after(client_ip)
        if retry_after:
            return _json_response(
                start_response,
                429,
                {"error": "Too many login attempts. Try again later."},
                [("Retry-After", str(retry_after))],
            )
        try:
            payload = _read_json(environ)
        except (ValueError, OverflowError) as error:
            return _json_response(start_response, 400 if isinstance(error, ValueError) else 413, {"error": str(error)})
        password = payload.get("password", "") if isinstance(payload, dict) else ""
        if not isinstance(password, str) or not verify_password(password, password_hash):
            _record_failed_login(client_ip)
            return _json_response(start_response, 401, {"error": "Invalid dashboard password"})
        _clear_login_failures(client_ip)
        cookie = (
            f"{SESSION_COOKIE}={_new_session_token()}; Path=/; Max-Age={SESSION_MAX_AGE}; "
            "Secure; HttpOnly; SameSite=Strict"
        )
        return _json_response(start_response, 200, {"authenticated": True}, [("Set-Cookie", cookie)])

    if method == "POST" and path == "/paypal/webhook":
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "")
        if not webhook_id or webhook_id.startswith("replace-"):
            return _json_response(start_response, 503, {"error": "PayPal webhook ID is not configured"})
        try:
            event = _read_json(environ)
            verification = paypal_request(
                "/v1/notifications/verify-webhook-signature",
                {
                    "auth_algo": environ.get("HTTP_PAYPAL_AUTH_ALGO"),
                    "cert_url": environ.get("HTTP_PAYPAL_CERT_URL"),
                    "transmission_id": environ.get("HTTP_PAYPAL_TRANSMISSION_ID"),
                    "transmission_sig": environ.get("HTTP_PAYPAL_TRANSMISSION_SIG"),
                    "transmission_time": environ.get("HTTP_PAYPAL_TRANSMISSION_TIME"),
                    "webhook_id": webhook_id,
                    "webhook_event": event,
                },
                access_token=get_paypal_access_token(),
            )
            if verification.get("verification_status") != "SUCCESS":
                return _json_response(start_response, 400, {"error": "PayPal webhook signature verification failed"})
            inserted = process_verified_webhook(monitor, event)
            return _json_response(start_response, 200, {"received": True, "duplicate": not inserted})
        except (ValueError, RuntimeError) as error:
            return _json_response(start_response, 503 if isinstance(error, RuntimeError) else 400, {"error": str(error)})

    if not _authenticated(environ):
        return _json_response(start_response, 401, {"error": "Authentication required"})
    if method != "GET" and not _origin_allowed(environ):
        return _json_response(start_response, 403, {"error": "Request origin is not allowed"})

    if method == "POST" and path == "/auth/logout":
        cookie = f"{SESSION_COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict"
        return _json_response(start_response, 200, {"authenticated": False}, [("Set-Cookie", cookie)])
    if method == "GET" and path == "/security/dashboard":
        return _json_response(start_response, 200, dashboard_snapshot(monitor))
    if method == "GET" and path == "/security/billing":
        return _json_response(start_response, 200, billing_snapshot(monitor))
    if method == "GET" and path == "/security/events.csv":
        if not has_feature(monitor, "exports"):
            return _json_response(start_response, 403, {"error": "CSV export requires an active Pro or Business license"})
        with monitor.database_lock:
            rows = monitor.database.execute(
                "SELECT occurred_at, event_type, source_ip, destination_ip, packet_count, window_seconds, details "
                "FROM network_events ORDER BY occurred_at DESC LIMIT 10000"
            ).fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "event_type", "source_ip", "destination_ip", "packet_count", "window_seconds", "details"])
        for row in rows:
            writer.writerow([datetime.fromtimestamp(row["occurred_at"]).astimezone().isoformat(), *list(row)[1:]])
        body = output.getvalue().encode("utf-8")
        start_response("200 OK", [
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Content-Disposition", "attachment; filename=vercyra-events.csv"),
            ("Cache-Control", "no-store"),
        ])
        return [body]
    if method == "POST" and path in {"/security/capture/start", "/security/capture/stop"}:
        return _json_response(start_response, 501, {"active": False, "error": "Packet capture is unavailable on this shared-hosting deployment"})
    if method == "POST" and path == "/billing/subscribe":
        try:
            payload = _read_json(environ)
            tier = payload.get("tier") if isinstance(payload, dict) else None
            if tier not in TIERS:
                raise ValueError("Select a supported plan")
            return _json_response(start_response, 200, _paypal_subscribe(tier))
        except (ValueError, RuntimeError, OverflowError) as error:
            status = 413 if isinstance(error, OverflowError) else 503 if isinstance(error, RuntimeError) else 400
            return _json_response(start_response, status, {"error": str(error)})

    return _json_response(start_response, 404, {"error": "Not found"})


if __name__ == "__main__":
    print(create_password_hash(getpass("Dashboard password: ")))
