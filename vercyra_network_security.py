import os
import sqlite3
import smtplib
import threading
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from pathlib import Path

from scapy.all import AsyncSniffer, IP, sniff

from vercyra_config import load_environment


load_environment()


class VercyraBusinessSecurity:
    THRESHOLD_LIMIT = 100
    TIME_WINDOW = 10
    DATABASE_PATH = Path(
        os.getenv(
            "VERCYRA_DATABASE_PATH",
            str(Path(__file__).with_name("vercyra_security.db")),
        )
    )

    def __init__(self):
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.alert_recipient = os.getenv("SMTP_RECIPIENT", self.smtp_user)
        self.traffic_tracker = defaultdict(deque)
        self.last_alert_time = {}
        self.database_lock = threading.Lock()
        self.database = sqlite3.connect(
            self.DATABASE_PATH, timeout=10, check_same_thread=False
        )
        self.database.row_factory = sqlite3.Row
        self.database.execute("PRAGMA journal_mode=WAL")
        self.database.execute("PRAGMA synchronous=NORMAL")
        self.database.executescript(
            """
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at REAL NOT NULL,
                event_type TEXT NOT NULL,
                source_ip TEXT,
                destination_ip TEXT,
                packet_count INTEGER,
                window_seconds INTEGER,
                details TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_network_events_time
                ON network_events(occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_network_events_source_time
                ON network_events(source_ip, occurred_at DESC);
            CREATE TABLE IF NOT EXISTS billing_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tier TEXT NOT NULL DEFAULT 'community',
                status TEXT NOT NULL DEFAULT 'TRIAL',
                subscription_id TEXT,
                plan_id TEXT,
                updated_at REAL NOT NULL
            );
            INSERT OR IGNORE INTO billing_state (id, updated_at)
                VALUES (1, unixepoch());
            CREATE TABLE IF NOT EXISTS paypal_webhooks (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                received_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS billing_simulator_events (
                event_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                event_type TEXT NOT NULL,
                received_at REAL NOT NULL
            );
            """
        )
        self.database.execute(
            "DELETE FROM network_events WHERE occurred_at < ?",
            (time.time() - 30 * 24 * 60 * 60,),
        )
        self.database.commit()
        self.sniffer = None
        self.capture_error = None
        self.event_count = 0

    def send_alert(self, threat_details):
        """Send an alert using the SMTP settings in the local .env file."""
        if (
            not self.smtp_user
            or not self.smtp_password
            or not self.alert_recipient
            or self.smtp_user == "your-email@gmail.com"
            or self.smtp_password == "your-app-specific-password"
        ):
            print("Alert not sent: configure SMTP_USER and SMTP_PASSWORD in .env.")
            return False

        message = EmailMessage()
        message.set_content(f"Alert: {threat_details}")
        message["Subject"] = "Vercyra Security Engine Notification"
        message["From"] = self.smtp_user
        message["To"] = self.alert_recipient

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException, ValueError) as error:
            print(f"Failed to send alert: {error}")
            return False

        return True

    def packet_callback(self, packet):
        """Log IP traffic and report high packet rates for each source."""
        if packet.haslayer(IP):
            ip_packet = packet[IP]
            source_ip = ip_packet.src
            destination_ip = ip_packet.dst
            current_time = time.time()
            print(f"[Traffic Log] {source_ip} -> {destination_ip}")
            self._store_event(
                current_time,
                "traffic",
                source_ip,
                destination_ip,
                details="IP packet observed",
            )

            packet_times = self.traffic_tracker[source_ip]
            window_start = current_time - self.TIME_WINDOW
            while packet_times and packet_times[0] <= window_start:
                packet_times.popleft()
            packet_times.append(current_time)

            last_alert = self.last_alert_time.get(source_ip, 0)
            if (
                len(packet_times) > self.THRESHOLD_LIMIT
                and current_time - last_alert >= self.TIME_WINDOW
            ):
                alert_message = (
                    "Potential high-volume connection event detected from "
                    f"source IP: {source_ip} ({len(packet_times)} packets "
                    f"in {self.TIME_WINDOW} seconds)"
                )
                print(f"[THREAT ALERT] {alert_message}")
                self.last_alert_time[source_ip] = current_time
                self._store_event(
                    current_time,
                    "threshold_alert",
                    source_ip,
                    destination_ip,
                    packet_count=len(packet_times),
                    window_seconds=self.TIME_WINDOW,
                    details=alert_message,
                )
                if self.smtp_user and self.smtp_password:
                    threading.Thread(
                        target=self.send_alert,
                        args=(alert_message,),
                        daemon=True,
                    ).start()

    def _store_event(
        self,
        occurred_at,
        event_type,
        source_ip=None,
        destination_ip=None,
        packet_count=None,
        window_seconds=None,
        details=None,
    ):
        """Persist only packet metadata; never store packet payloads."""
        with self.database_lock:
            self.database.execute(
                """
                INSERT INTO network_events (
                    occurred_at, event_type, source_ip, destination_ip,
                    packet_count, window_seconds, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    occurred_at,
                    event_type,
                    source_ip,
                    destination_ip,
                    packet_count,
                    window_seconds,
                    details,
                ),
            )
            self.event_count += 1
            if self.event_count % 500 == 0:
                self.database.execute(
                    "DELETE FROM network_events WHERE occurred_at < ?",
                    (occurred_at - 30 * 24 * 60 * 60,),
                )
            self.database.commit()

    def start_capture(self):
        """Begin packet capture on explicit local API request."""
        if self.sniffer is not None and self.sniffer.running:
            return self.capture_status()
        self.capture_error = None
        try:
            self.sniffer = AsyncSniffer(prn=self.packet_callback, store=False)
            self.sniffer.start()
        except Exception as error:
            self.capture_error = str(error)
            self.sniffer = None
        return self.capture_status()

    def stop_capture(self):
        if self.sniffer is not None and self.sniffer.running:
            try:
                self.sniffer.stop(join=True)
            except Exception as error:
                self.capture_error = str(error)
        return self.capture_status()

    def capture_status(self):
        if self.sniffer is not None and self.sniffer.exception is not None:
            self.capture_error = str(self.sniffer.exception)
        return {
            "active": bool(self.sniffer and self.sniffer.running),
            "error": self.capture_error,
        }

    def close(self):
        self.stop_capture()
        with self.database_lock:
            self.database.close()

    def start_automatic_bg_agent(self):
        """Capture packets until interrupted by the operator."""
        print("Vercyra Background Security Agent Active...")
        sniff(prn=self.packet_callback, store=0)


if __name__ == "__main__":
    suite = VercyraBusinessSecurity()
    suite.start_automatic_bg_agent()
