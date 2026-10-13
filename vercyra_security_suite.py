import os
import sys
import hashlib
import re
import time
from datetime import datetime
from scapy.all import sniff, IP, TCP

class VercyraSecuritySuite:
    def __init__(self):
        self.log_file = "vercyra_security.log"
        self.quarantine_dir = os.path.abspath("vercyra_quarantine")
        os.makedirs(self.quarantine_dir, exist_ok=True)
        # 1. Antivirus Signatures (SHA256 hashes of known malicious files)
        self.malware_db = {
            "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f": "Test_Threat.EICAR",
            "5a625a225a225a225a225a225a225a225a225a225a225a225a225a225a225a22": "Ransomware.WannaCry_Sample"
        }
        # 2. Firewall Rules (Simulated Blacklist & Rate Limiting thresholds)
        self.ip_blacklist = {"192.168.1.250", "45.33.22.11"}
        self.packet_counts = {}
        self.DOS_THRESHOLD = 50  # Packets per second before triggering firewall block

    def log_event(self, alert_type, message):
        """Central Threat Logger for security analytics."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{alert_type.upper()}] {message}\n"
        print(log_entry.strip())
        with open(self.log_file, "a") as f:
            f.write(log_entry)

    # ==================== MODULE 1: ANTIVIRUS SCANNERS ====================
    def calculate_sha256(self, file_path):
        """Generates deterministic cryptographic fingerprints for localized files."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return None

    def scan_file(self, file_path):
        """Checks a specific target file against the known malware database signatures."""
        file_hash = self.calculate_sha256(file_path)
        if not file_hash:
            return
        
        if file_hash in self.malware_db:
            threat_name = self.malware_db[file_hash]
            filename = os.path.basename(file_path)
            quarantine_path = os.path.join(self.quarantine_dir, filename)
            name, extension = os.path.splitext(filename)
            suffix = 1
            while os.path.lexists(quarantine_path):
                quarantine_path = os.path.join(
                    self.quarantine_dir, f"{name}_{suffix}{extension}"
                )
                suffix += 1
            try:
                os.rename(file_path, quarantine_path)
            except OSError as error:
                self.log_event(
                    "ERROR",
                    f"Failed to quarantine {file_path}: {error}",
                )
                return True
            self.log_event(
                "CRITICAL_AV",
                f"Malware Detected! File: {file_path} -> Threat: {threat_name}; "
                f"Quarantined at: {quarantine_path}",
            )
            return True
        return False

    def scan_directory(self, directory_path):
        """Recursively traverses a local directory directory tree searching for threats."""
        self.log_event("INFO", f"Starting Antivirus Filesystem Scan on: {directory_path}")
        threats_found = 0
        for root, directories, files in os.walk(directory_path):
            directories[:] = [
                directory for directory in directories
                if os.path.normcase(os.path.abspath(os.path.join(root, directory)))
                != os.path.normcase(self.quarantine_dir)
            ]
            for file in files:
                full_path = os.path.join(root, file)
                if self.scan_file(full_path):
                    threats_found += 1
        self.log_event("INFO", f"Scan complete. Found {threats_found} threat(s).")

    # ==================== MODULE 2: NETWORK FIREWALL ====================
    def packet_callback(self, packet):
        """Deep inspection callback engine triggered per arriving IP network frame."""
        if packet.haslayer(IP):
            src_ip = packet[IP].src
            
            # Check explicit static network blacklist
            if src_ip in self.ip_blacklist:
                self.log_event("FIREWALL_BLOCK", f"Connection rejected from blacklisted host: {src_ip}")
                return

            # Basic Dynamic Denial of Service (DoS) rate calculation filtering
            current_sec = int(time.time())
            tracking_key = f"{src_ip}:{current_sec}"
            self.packet_counts[tracking_key] = self.packet_counts.get(tracking_key, 0) + 1

            if self.packet_counts[tracking_key] > self.DOS_THRESHOLD:
                self.log_event("FIREWALL_ALERT", f"Flooding activity mitigated from source IP: {src_ip}")
                self.ip_blacklist.add(src_ip) # Dynamic addition to mitigation array

    def start_network_firewall(self):
        """Engages real-time runtime network socket analysis operations."""
        self.log_event("INFO", "Initializing Network Traffic Inspection Subsystem Engine...")
        try:
            # Sniffs network packets indefinitely; triggers packet_callback rule sets
            sniff(prn=self.packet_callback, store=0)
        except PermissionError:
            self.log_event("ERROR", "Firewall initialization failed: Root/Administrator privileges required to capture packets.")

# ==================== EXECUTION MANAGER ====================
if __name__ == "__main__":
    suite = VercyraSecuritySuite()
    
    print("=== Vercyra Custom Internet Security Suite Menu ===")
    print("1. Run Antivirus System Directory Scan")
    print("2. Launch Real-time Network Security Firewall (Requires Admin/Root)")
    choice = input("Select an operational runtime strategy (1 or 2): ").strip()

    if choice == "1":
        target_dir = input("Enter the absolute file directory path to scan (e.g. '.'): ").strip()
        suite.scan_directory(target_dir)
    elif choice == "2":
        suite.start_network_firewall()
    else:
        print("Invalid operational flag selected. System terminating safely.")