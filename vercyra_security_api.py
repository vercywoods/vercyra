import base64
import csv
import io
import json
import os
import secrets
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from vercyra_network_security import VercyraBusinessSecurity

TIERS = {
    "starter": {
        "name": "Starter",
        "plan_env": "PAYPAL_PLAN_STARTER",
        "features": ["monitoring", "alerts"],
    },
    "pro": {
        "name": "Pro",
        "plan_env": "PAYPAL_PLAN_PRO",
        "features": ["monitoring", "alerts", "exports"],
    },
    "business": {
        "name": "Business",
        "plan_env": "PAYPAL_PLAN_BUSINESS",
        "features": ["monitoring", "alerts", "exports", "extended_retention"],
    },
}
ACTIVE_STATUSES = {"ACTIVE", "SIMULATED_ACTIVE"}
PAYPAL_ENVIRONMENTS = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com",
}


def paypal_base_url():
    environment = os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower()
    if environment not in PAYPAL_ENVIRONMENTS:
        raise ValueError("PAYPAL_ENVIRONMENT must be sandbox or live")
    return PAYPAL_ENVIRONMENTS[environment]


def paypal_credentials():
    client_id = os.getenv("PAYPAL_CLIENT_ID", "")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
    if (
        not client_id
        or not client_secret
        or client_id.startswith("replace-")
        or client_secret.startswith("replace-")
    ):
        raise RuntimeError("PayPal REST credentials are not configured")
    return client_id, client_secret


def paypal_request(path, payload=None, access_token=None):
    client_id, client_secret = paypal_credentials()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    data = json.dumps(payload).encode() if payload is not None else b"grant_type=client_credentials"
    if payload is None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(
        f"{paypal_base_url()}{path}",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("PayPal request failed") from error


def get_paypal_access_token():
    response = paypal_request("/v1/oauth2/token")
    token = response.get("access_token")
    if not token:
        raise RuntimeError("PayPal did not return an access token")
    return token


def configured_plans():
    return {
        tier: os.getenv(config["plan_env"], "")
        for tier, config in TIERS.items()
    }


def enabled_simulators():
    if os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower() == "live":
        return []
    if os.getenv("BILLING_SIMULATOR_ENABLED", "false").lower() != "true":
        return []
    return [
        provider
        for provider in ("paypal", "stripe")
        if os.getenv(f"{provider.upper()}_SIMULATOR_ENABLED", "false").lower() == "true"
    ]


def billing_snapshot(monitor):
    with monitor.database_lock:
        row = monitor.database.execute(
            "SELECT tier, status, subscription_id, plan_id, updated_at "
            "FROM billing_state WHERE id = 1"
        ).fetchone()
    tier = row["tier"] if row else "community"
    status = row["status"] if row else "TRIAL"
    tier_config = TIERS.get(tier)
    plans = configured_plans()
    simulator_providers = enabled_simulators()
    paypal_values = [
        os.getenv("PAYPAL_CLIENT_ID", ""),
        os.getenv("PAYPAL_CLIENT_SECRET", ""),
        os.getenv("PAYPAL_WEBHOOK_ID", ""),
    ]
    client_ready = all(value and not value.startswith("replace-") for value in paypal_values)
    plan_ready = any(value and not value.startswith("replace-") for value in plans.values())
    environment = os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower()
    public_url = urlparse(os.getenv("VERCYRA_PUBLIC_URL", ""))
    webhook_url = urlparse(os.getenv("PAYPAL_WEBHOOK_URL", ""))
    live_urls_ready = (
        environment != "live"
        or (
            public_url.scheme == "https"
            and bool(public_url.netloc)
            and "replace-" not in public_url.netloc
            and webhook_url.scheme == "https"
            and bool(webhook_url.netloc)
            and "replace-" not in webhook_url.netloc
        )
    )
    return {
        "tier": tier,
        "tier_name": tier_config["name"] if tier_config else "Community",
        "status": status,
        "subscription_id": row["subscription_id"] if row else None,
        "provider": (
            row["plan_id"].split(":", 1)[1]
            if row and row["plan_id"] and row["plan_id"].startswith("SIMULATOR:")
            else "paypal" if row and row["plan_id"] else None
        ),
        "updated_at": row["updated_at"] if row else None,
        "features": tier_config["features"] if tier_config and status in ACTIVE_STATUSES else ["monitoring", "alerts"],
        "paypal_ready": client_ready and plan_ready and live_urls_ready,
        "simulation_providers": simulator_providers,
        "environment": environment,
        "plans": [
            {
                "id": key,
                "name": config["name"],
                "available": bool(plans[key]) and not plans[key].startswith("replace-"),
            }
            for key, config in TIERS.items()
        ],
    }


def dashboard_snapshot(monitor):
    now = time.time()
    with monitor.database_lock:
        database = monitor.database
        totals = database.execute(
            """SELECT
                COUNT(*) AS packets,
                COUNT(DISTINCT source_ip) AS sources
            FROM network_events
            WHERE event_type = 'traffic' AND occurred_at >= ?""",
            (now - 24 * 60 * 60,),
        ).fetchone()
        alert_count = database.execute(
            "SELECT COUNT(*) FROM network_events "
            "WHERE event_type = 'threshold_alert' AND occurred_at >= ?",
            (now - 24 * 60 * 60,),
        ).fetchone()[0]
        recent_rate = database.execute(
            "SELECT COUNT(*) FROM network_events "
            "WHERE event_type = 'traffic' AND occurred_at >= ?",
            (now - 10,),
        ).fetchone()[0]
        recent_rows = database.execute(
            """SELECT occurred_at, event_type, source_ip, destination_ip,
                      packet_count, window_seconds, details
            FROM network_events ORDER BY occurred_at DESC LIMIT 60"""
        ).fetchall()
        grouped = database.execute(
            """SELECT CAST(occurred_at / 300 AS INTEGER) * 300 AS bucket,
                      SUM(CASE WHEN event_type = 'traffic' THEN 1 ELSE 0 END) AS packets,
                      SUM(CASE WHEN event_type = 'threshold_alert' THEN 1 ELSE 0 END) AS alerts
            FROM network_events WHERE occurred_at >= ? GROUP BY bucket""",
            (now - 60 * 60,),
        ).fetchall()

    by_bucket = {int(row["bucket"]): row for row in grouped}
    chart = []
    last_bucket = int(now // 300) * 300
    for offset in range(11, -1, -1):
        bucket = last_bucket - offset * 300
        row = by_bucket.get(bucket)
        chart.append({
            "time": bucket,
            "packets": int(row["packets"]) if row else 0,
            "alerts": int(row["alerts"]) if row else 0,
        })

    return {
        "generated_at": now,
        "metrics": {
            "packets_24h": int(totals["packets"] or 0),
            "unique_sources_24h": int(totals["sources"] or 0),
            "alerts_24h": int(alert_count),
            "packets_10s": int(recent_rate),
        },
        "chart": chart,
        "events": [
            {
                "id": row["occurred_at"],
                "time": datetime.fromtimestamp(row["occurred_at"]).astimezone().isoformat(timespec="seconds"),
                "event_type": row["event_type"],
                "source_ip": row["source_ip"],
                "destination_ip": row["destination_ip"],
                "packet_count": row["packet_count"],
                "window_seconds": row["window_seconds"],
                "details": row["details"],
            }
            for row in recent_rows
        ],
        "capture": monitor.capture_status(),
        "billing": billing_snapshot(monitor),
        "database": os.path.basename(str(monitor.DATABASE_PATH)),
    }


def has_feature(monitor, feature):
    billing = billing_snapshot(monitor)
    return billing["status"] in ACTIVE_STATUSES and feature in billing["features"]


def process_simulated_webhook(monitor, payload):
    if not enabled_simulators():
        raise PermissionError("Local billing simulation is disabled")
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    provider = str(payload.get("provider", "")).lower()
    if provider not in enabled_simulators():
        raise ValueError("That provider simulator is not enabled")
    tier = payload.get("tier")
    if tier not in TIERS:
        raise ValueError("Select a supported plan")
    action = str(payload.get("action", "activate")).lower()
    if action not in {"activate", "cancel"}:
        raise ValueError("Supported simulator events are activate and cancel")

    with monitor.database_lock:
        current = monitor.database.execute(
            "SELECT status, subscription_id, plan_id FROM billing_state WHERE id = 1"
        ).fetchone()
        if action == "cancel":
            if (
                not current
                or current["status"] != "SIMULATED_ACTIVE"
                or current["plan_id"] != f"SIMULATOR:{provider}"
            ):
                raise ValueError("No simulated subscription for that provider is active")
            subscription_id = current["subscription_id"]
            status = "SIMULATED_CANCELLED"
            event_type = "SIMULATOR.SUBSCRIPTION.CANCELLED"
        else:
            if current and current["status"] == "ACTIVE":
                raise ValueError("Cannot replace a real active subscription with a simulated one")
            subscription_id = f"SIM-{provider.upper()}-{secrets.token_hex(6)}"
            status = "SIMULATED_ACTIVE"
            event_type = "SIMULATOR.SUBSCRIPTION.ACTIVATED"

        event_id = f"SIM-{provider.upper()}-{secrets.token_hex(12)}"
        monitor.database.execute(
            "INSERT INTO billing_simulator_events (event_id, provider, event_type, received_at) "
            "VALUES (?, ?, ?, ?)",
            (event_id, provider, event_type, time.time()),
        )
        monitor.database.execute(
            """UPDATE billing_state SET tier = ?, status = ?, subscription_id = ?,
                plan_id = ?, updated_at = ? WHERE id = 1""",
            (tier, status, subscription_id, f"SIMULATOR:{provider}", time.time()),
        )
        monitor.database.commit()

    return {
        "accepted": True,
        "simulated": True,
        "provider": provider,
        "tier": tier,
        "status": status,
        "subscription_id": subscription_id,
        "event_id": event_id,
    }


def process_verified_webhook(monitor, event):
    event_id = event.get("id")
    event_type = event.get("event_type", "")
    resource = event.get("resource") or {}
    if not event_id:
        raise ValueError("Webhook event is missing its id")

    updates = {
        "BILLING.SUBSCRIPTION.ACTIVATED": "ACTIVE",
        "BILLING.SUBSCRIPTION.UPDATED": resource.get("status", "ACTIVE"),
        "BILLING.SUBSCRIPTION.CANCELLED": "CANCELLED",
        "BILLING.SUBSCRIPTION.SUSPENDED": "SUSPENDED",
        "BILLING.SUBSCRIPTION.EXPIRED": "EXPIRED",
        "PAYMENT.SALE.DENIED": "PAST_DUE",
        "PAYMENT.CAPTURE.DENIED": "PAST_DUE",
    }

    with monitor.database_lock:
        cursor = monitor.database.execute(
            "INSERT OR IGNORE INTO paypal_webhooks (event_id, event_type, received_at) "
            "VALUES (?, ?, ?)",
            (event_id, event_type, time.time()),
        )
        if cursor.rowcount == 0:
            monitor.database.commit()
            return False

        status = updates.get(event_type)
        subscription_id = resource.get("id") or resource.get("billing_agreement_id")
        if status and subscription_id:
            status = str(status).upper()
            plan_id = resource.get("plan_id")
            tier = next(
                (name for name, configured in configured_plans().items() if configured and configured == plan_id),
                "community",
            )
            monitor.database.execute(
                """UPDATE billing_state SET tier = ?, status = ?, subscription_id = ?,
                    plan_id = ?, updated_at = ? WHERE id = 1""",
                (tier, status, subscription_id, plan_id, time.time()),
            )
        monitor.database.commit()
    return True


class SecurityAPIHandler(BaseHTTPRequestHandler):
    server_version = "VercyraLocalAPI/1.0"

    @property
    def monitor(self):
        return self.server.monitor

    def log_message(self, format_string, *args):
        print(f"[API] {self.address_string()} {format_string % args}")

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length < 0 or length > 256_000:
            raise ValueError("Request body is too large")
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            raise ValueError("Invalid JSON body") from error

    def local_request(self):
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        return host in {"localhost", "127.0.0.1"}

    def do_GET(self):
        if not self.local_request():
            return self.send_json(403, {"error": "Local requests only"})
        if self.path == "/api/health":
            return self.send_json(200, {"status": "ok"})
        if self.path == "/api/security/dashboard":
            return self.send_json(200, dashboard_snapshot(self.monitor))
        if self.path == "/api/security/billing":
            return self.send_json(200, billing_snapshot(self.monitor))
        if self.path == "/api/security/events.csv":
            if not has_feature(self.monitor, "exports"):
                return self.send_json(403, {"error": "CSV export requires an active Pro or Business license"})
            with self.monitor.database_lock:
                rows = self.monitor.database.execute(
                    "SELECT occurred_at, event_type, source_ip, destination_ip, packet_count, window_seconds, details "
                    "FROM network_events ORDER BY occurred_at DESC LIMIT 10000"
                ).fetchall()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["timestamp", "event_type", "source_ip", "destination_ip", "packet_count", "window_seconds", "details"])
            for row in rows:
                writer.writerow([datetime.fromtimestamp(row["occurred_at"]).astimezone().isoformat(), *list(row)[1:]])
            body = output.getvalue().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=vercyra-events.csv")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/api/paypal/webhook":
            return self.handle_paypal_webhook()
        if not self.local_request():
            return self.send_json(403, {"error": "Local requests only"})
        if self.path == "/api/security/capture/start":
            return self.send_json(200, self.monitor.start_capture())
        if self.path == "/api/security/capture/stop":
            return self.send_json(200, self.monitor.stop_capture())
        if self.path == "/api/billing/subscribe":
            return self.handle_subscribe()
        if self.path == "/api/billing/simulator/webhook":
            return self.handle_simulated_webhook()
        self.send_json(404, {"error": "Not found"})

    def handle_simulated_webhook(self):
        try:
            result = process_simulated_webhook(self.monitor, self.read_json())
            self.send_json(200, result)
        except PermissionError as error:
            self.send_json(403, {"error": str(error)})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})

    def handle_subscribe(self):
        try:
            payload = self.read_json()
            tier = payload.get("tier") if isinstance(payload, dict) else None
            if tier not in TIERS:
                return self.send_json(400, {"error": "Select a supported plan"})
            plan_id = os.getenv(TIERS[tier]["plan_env"], "")
            if not plan_id or plan_id.startswith("replace-"):
                return self.send_json(503, {"error": "PayPal plan IDs are not configured"})
            environment = os.getenv("PAYPAL_ENVIRONMENT", "sandbox").lower()
            if environment == "live":
                public_url = urlparse(os.getenv("VERCYRA_PUBLIC_URL", ""))
                webhook_url = urlparse(os.getenv("PAYPAL_WEBHOOK_URL", ""))
                if (
                    public_url.scheme != "https"
                    or not public_url.netloc
                    or "replace-" in public_url.netloc
                    or webhook_url.scheme != "https"
                    or not webhook_url.netloc
                    or "replace-" in webhook_url.netloc
                ):
                    return self.send_json(
                        503,
                        {"error": "Live PayPal checkout requires public HTTPS return and webhook URLs"},
                    )
            token = get_paypal_access_token()
            base_url = os.getenv("VERCYRA_PUBLIC_URL", "http://localhost:4173").rstrip("/")
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
                return self.send_json(502, {"error": "PayPal did not return an approval URL"})
            self.send_json(200, {"approval_url": approval_url, "subscription_id": response.get("id")})
        except (ValueError, RuntimeError) as error:
            self.send_json(400 if isinstance(error, ValueError) else 503, {"error": str(error)})

    def handle_paypal_webhook(self):
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "")
        if not webhook_id or webhook_id.startswith("replace-"):
            return self.send_json(503, {"error": "PayPal webhook ID is not configured"})
        try:
            event = self.read_json()
            token = get_paypal_access_token()
            verification = paypal_request(
                "/v1/notifications/verify-webhook-signature",
                {
                    "auth_algo": self.headers.get("PAYPAL-AUTH-ALGO"),
                    "cert_url": self.headers.get("PAYPAL-CERT-URL"),
                    "transmission_id": self.headers.get("PAYPAL-TRANSMISSION-ID"),
                    "transmission_sig": self.headers.get("PAYPAL-TRANSMISSION-SIG"),
                    "transmission_time": self.headers.get("PAYPAL-TRANSMISSION-TIME"),
                    "webhook_id": webhook_id,
                    "webhook_event": event,
                },
                access_token=token,
            )
            if verification.get("verification_status") != "SUCCESS":
                return self.send_json(400, {"error": "PayPal webhook signature verification failed"})
            inserted = process_verified_webhook(self.monitor, event)
            self.send_json(200, {"received": True, "duplicate": not inserted})
        except (ValueError, RuntimeError) as error:
            self.send_json(400 if isinstance(error, ValueError) else 503, {"error": str(error)})


def main():
    monitor = VercyraBusinessSecurity()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), SecurityAPIHandler)
    server.monitor = monitor
    print("Vercyra local security API listening at http://127.0.0.1:8765")
    print(f"SQLite metadata store: {monitor.DATABASE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping local security API...")
    finally:
        server.server_close()
        monitor.close()


if __name__ == "__main__":
    main()