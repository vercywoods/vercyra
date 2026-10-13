import os
import sys
import hashlib
import time
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


class VercyraSecureProHandler(FileSystemEventHandler):
    """Real-Time Agent that catches files dynamically as they drop into folders."""

    def __init__(self, scanner_instance):
        self.scanner = scanner_instance

    def on_created(self, event):
        if not event.is_directory:
            self.scanner.process_realtime_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.scanner.process_realtime_file(event.src_path)


class VercyraBusinessSecuritySuite:
    def __init__(self, client_license_key="DEMO_UNPAID"):
        self.watch_directory = "."
        self.quarantine_directory = "./vercyra_quarantine"
        self.log_file = "vercyra_security.log"
        self.smtp_server = os.environ.get(
            "SMTP_SERVER", os.environ.get("VERCYRA_SMTP_SERVER", "smtp.gmail.com")
        )
        self.smtp_port = int(
            os.environ.get("SMTP_PORT", os.environ.get("VERCYRA_SMTP_PORT", "587"))
        )
        self.sender_email = os.environ.get(
            "SMTP_USER", os.environ.get("VERCYRA_SMTP_USERNAME", "")
        )
        self.sender_password = os.environ.get(
            "SMTP_PASSWORD", os.environ.get("VERCYRA_SMTP_PASSWORD", "")
        )
        self.receiver_email = os.environ.get(
            "SMTP_RECIPIENT",
            os.environ.get("VERCYRA_ALERT_RECIPIENT", "ceciliaaudrey334@gmail.com"),
        )

        # Safe mock database of known threat signatures
        self.malware_signatures = {
            "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f": "Test_Threat.EICAR",
            "5a625a225a225a225a225a225a225a225a225a225a225a225a225a225a225a22": "Ransomware.WannaCry_Sample"
        }

        # B2B Monetization Engine (Commercial Licensing Tier Parameters)
        self.client_license = client_license_key
        self.scan_count = 0
        self.MAX_FREE_SCANS = 5  # The limit of free checks before they must buy a subscription
        self.license_limit_reported = False

        # Ensure your quarantine vault directory exists safely
        os.makedirs(self.quarantine_directory, exist_ok=True)

    def send_email_alert(self, filename, threat_type, quarantine_path):
        """Send an incident summary after the file has been quarantined."""
        if (
            not self.sender_email
            or not self.sender_password
            or not self.receiver_email
            or self.sender_email == "your-email@gmail.com"
            or self.sender_password == "your-app-specific-password"
        ):
            self.log_incident(
                "WARNING",
                "Email alert not sent; configure SMTP_USER, SMTP_PASSWORD, "
                "and SMTP_RECIPIENT in the local .env file.",
            )
            return

        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = "Vercyra Security Alert: Threat Quarantined"
        message.attach(
            MIMEText(
                "A matching file was moved to quarantine.\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"File: {filename}\n"
                f"Threat: {threat_type}\n"
                f"Quarantine path: {quarantine_path}\n",
                "plain",
            )
        )

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException, ValueError) as error:
            self.log_incident(
                "WARNING", f"Failed to dispatch email notification: {error}"
            )
            return

        self.log_incident(
            "INFO", f"Email alert sent successfully to {self.receiver_email}"
        )

    def verify_billing_status(self):
        """Monetization Guard: Verifies license validation limits or logs billing metrics."""
        if self.client_license == "DEMO_UNPAID":
            if self.scan_count >= self.MAX_FREE_SCANS:
                if not self.license_limit_reported:
                    print(f"\n[$$$] LICENSE LIMIT EXCEEDED: Client usage reached {self.scan_count}/{self.MAX_FREE_SCANS} free checks.")
                    print("[$$$] ACTION REQUIRED: Upgrade Vercyra Shield to Premium License to re-enable continuous security monitoring.")
                    self.license_limit_reported = True
                return False
            else:
                remaining = self.MAX_FREE_SCANS - self.scan_count
                print(f"[COMMERCIAL LOG] Active Tier: Free Trial Mode. Remaining safe usage operations: {remaining}.")
        else:
            print(f"[COMMERCIAL LOG] Active Tier: Enterprise Premium Key [{self.client_license}] - Status: Active & Billing.")
        return True

    def log_incident(self, classification, message):
        """Central database log writer for threat analytics reports."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{classification.upper()}] {message}\n"
        print(entry.strip())
        with open(self.log_file, "a") as f:
            f.write(entry)

    def calculate_file_hash(self, file_path):
        """Generates deterministic cryptographic fingerprints for local file analysis."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (PermissionError, FileNotFoundError):
            return None

    def process_realtime_file(self, file_path):
        """Main execution gateway handling threat validation and automated file quarantine."""
        # Check monetization barriers before processing data overhead
        if not self.verify_billing_status():
            return

        # Avoid scanning files that are already inside the quarantine vault
        normalized_path = os.path.normcase(os.path.abspath(file_path))
        quarantine_root = os.path.normcase(os.path.abspath(self.quarantine_directory))
        try:
            if os.path.commonpath((normalized_path, quarantine_root)) == quarantine_root:
                return
        except ValueError:
            pass
        log_path = os.path.normcase(os.path.abspath(self.log_file))
        if normalized_path == log_path:
            return

        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return

        self.scan_count += 1  # Record business usage for billing transparency

        if file_hash in self.malware_signatures:
            threat_id = self.malware_signatures[file_hash]
            filename = os.path.basename(file_path)
            quarantine_destination = os.path.join(self.quarantine_directory, f"QUARANTINED_{int(time.time())}_{filename}")

            try:
                # Automate file quarantine by stripping the file out of active workspace
                shutil.move(file_path, quarantine_destination)
                self.log_incident(
                    "CRITICAL_QUARANTINE",
                    f"Isolated file '{filename}' to '{quarantine_destination}'. "
                    f"Detected as: {threat_id}",
                )
                self.send_email_alert(filename, threat_id, quarantine_destination)
            except Exception as e:
                self.log_incident("SYSTEM_ERROR", f"Failed to isolate threatened file path: {str(e)}")

    def start_automatic_bg_agent(self):
        """Launches the continuous background watcher daemon process."""
        self.log_incident("SYSTEM_STARTUP", f"Vercyra Active Shield Engine activated in continuous monitoring mode.")
        print(f"[*] Guarding workspace directory: '{self.watch_directory}'...")
        print("[*] Keep this window running in the background. Press Ctrl+C to terminate safely.\n" + "="*70)

        event_handler = VercyraSecureProHandler(self)
        observer = Observer()
        observer.schedule(event_handler, path=self.watch_directory, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1) # Keeps background monitoring loop alive efficiently
        except KeyboardInterrupt:
            observer.stop()
            self.log_incident("SYSTEM_SHUTDOWN", "Security suite background monitor stopped safely by operator.")
        observer.join()


if __name__ == "__main__":
    # To simulate selling this software to a paying enterprise client:
    # Pass their unique subscription ID string as an argument, e.g.: VercyraBusinessSecuritySuite("LICENSE_PREMIUM_9948X")
    # Leave empty or pass "DEMO_UNPAID" to see how your built-in payment wall monetization mechanism blocks free exploit usage.

    suite = VercyraBusinessSecuritySuite(client_license_key="DEMO_UNPAID")
    suite.start_automatic_bg_agent()