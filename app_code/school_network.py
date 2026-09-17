"""Read-only, fail-closed checks of the host's school network connection."""
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
import platform
import re
import threading
from .system_tools import run_command

VPN_PORTAL = "vpn.connect.cpp.edu"
APPROVED_SSIDS = {"eduroam"}
WARNING = f"School login unavailable: connect GlobalProtect to {VPN_PORTAL} or join eduroam, then check again."


def parse_vpn_status(text):
    """Read the last reported state, not a remembered portal configuration."""
    connected = False
    portal = ""
    for block in re.findall(r"<response>.*?</response>", text, re.S):
        try:
            root = ET.fromstring(block)
        except ET.ParseError:
            continue
        if root.findtext("type") != "status":
            continue
        states = [root.findtext(tag) for tag in ("status", "state") if root.findtext(tag)]
        if states:
            connected = all(value.strip().lower() == "connected" for value in states)
            if not connected:
                portal = ""
        reported_portal = root.findtext("portal")
        if reported_portal is not None:
            portal = reported_portal.strip() if connected else ""
    try:
        address = urlsplit(portal if "://" in portal else "https://" + portal)
        matches = (address.hostname or "").lower() == VPN_PORTAL and address.username is None and address.password is None
    except ValueError:
        matches = False
    return connected and matches


def vpn_portal_confirmed(system):
    # Read only the bounded tail of the client's status log. Never copy or
    # display its contents: it can contain account or authentication details.
    if system == "Darwin":
        path = Path.home() / "Library/Logs/PaloAltoNetworks/GlobalProtect/PanGPA.log"
    elif system == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return False
        path = Path(local) / "PaloAltoNetworks/GlobalProtect/PanGPA.log"
    else:
        return False
    try:
        with path.open("rb") as source:
            source.seek(0, 2)
            source.seek(max(0, source.tell() - 1024 * 1024))
            return parse_vpn_status(source.read().decode("utf-8", errors="replace"))
    except OSError:
        return False


def detect_school_network(system=None, run=run_command, portal_check=vpn_portal_confirmed):
    system = system or platform.system()

    def read(arguments, timeout=8):
        try:
            return run(arguments, timeout=timeout)
        except Exception:
            # Missing tools, permissions, timeouts and unavailable interfaces
            # all leave login disabled unless another check succeeds.
            return ""

    if system == "Windows":
        # Require the GlobalProtect virtual adapter to be up with an assigned
        # address, not merely an installed/running GlobalProtect application.
        script = (
            "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and "
            "$_.InterfaceDescription -match 'PANGP|Palo Alto|GlobalProtect' } | "
            "ForEach-Object { Get-NetIPAddress -InterfaceIndex $_.ifIndex "
            "-AddressFamily IPv4 -ErrorAction SilentlyContinue } | "
            "Where-Object { $_.AddressState -eq 'Preferred' -and "
            "$_.IPAddress -notmatch '^(169\\.254\\.|127\\.|0\\.)' } | "
            "ForEach-Object { 'QM_GP_CONNECTED' }"
        )
        if "QM_GP_CONNECTED" in read(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]).splitlines() and portal_check(system):
            return True, f"Connected VPN: GlobalProtect ({VPN_PORTAL}) | School login available"
        wifi = read(["netsh", "wlan", "show", "interfaces"])
        for block in re.split(r"(?im)^\s*Name\s*:", wifi):
            if re.search(r"(?im)^\s*State\s*:\s*connected\s*$", block):
                match = re.search(r"(?im)^\s*SSID\s*:\s*(.*?)\s*$", block)
                if match and match[1] in APPROVED_SSIDS:
                    return True, "Connected Wi-Fi: " + match[1] + " | School login available"
    elif system == "Darwin":
        services = read(["/usr/sbin/scutil", "--nc", "list"])
        for line in services.splitlines():
            if "(Connected)" in line and re.search(r"GlobalProtect|Palo Alto|com\.paloaltonetworks", line, re.I) and portal_check(system):
                return True, f"Connected VPN: GlobalProtect ({VPN_PORTAL}) | School login available"
        # GlobalProtect commonly registers a dynamic-store service rather than
        # a Network Preferences VPN. Verify its named service AND live IPv4 state.
        # scutil takes its dynamic-store queries on stdin (see helper below).
        state = read(["/bin/sh", "-c", "printf 'show State:/Network/Service/gpd.pan/IPv4\\n' | /usr/sbin/scutil"])
        interface = re.search(r"InterfaceName\s*:\s*(utun\d+|gpd\d+)", state)
        if interface:
            details = read(["/sbin/ifconfig", interface[1]])
            if re.search(r"flags=.*<[^>]*\bUP\b", details) and re.search(r"\binet\s+(?!169\.254\.|127\.|0\.)\d+\.\d+\.\d+\.\d+", details) and portal_check(system):
                return True, f"Connected VPN: GlobalProtect ({VPN_PORTAL}) | School login available"
        ports = read(["/usr/sbin/networksetup", "-listallhardwareports"])
        for device in re.findall(r"Hardware Port: (?:Wi-Fi|AirPort)\s+Device: (\S+)", ports):
            wifi = read(["/usr/sbin/networksetup", "-getairportnetwork", device])
            match = re.search(r"Current (?:Wi-Fi|AirPort) Network:\s*(.*?)\s*$", wifi)
            if match and match[1] in APPROVED_SSIDS:
                return True, "Connected Wi-Fi: " + match[1] + " | School login available"
        # On recent macOS releases networksetup can report "not associated"
        # even while Wi-Fi is connected. Only inspect the CURRENT network in
        # System Profiler, never its list of nearby or remembered networks.
        report = read(["/usr/sbin/system_profiler", "SPAirPortDataType", "-json", "-timeout", "30"], timeout=40)
        try:
            data = json.loads(report)
            for group in data.get("SPAirPortDataType", []):
                for interface in group.get("spairport_airport_interfaces", []):
                    if interface.get("spairport_status_information") != "spairport_status_connected":
                        continue
                    ssid = interface.get("spairport_current_network_information", {}).get("_name")
                    if isinstance(ssid, str) and ssid in APPROVED_SSIDS:
                        return True, "Connected Wi-Fi: " + ssid + " | School login available"
        except (ValueError, TypeError, AttributeError):
            pass
    return False, WARNING


class SchoolNetworkControls:
    def check_school_network(self):
        if self.network_checking:
            return
        self.network_checking = True
        self.network_status.set("Checking GlobalProtect (vpn.connect.cpp.edu), then eduroam…")
        self.update_controls()

        def check():
            self.events.put(("network_checked", detect_school_network()))
        threading.Thread(target=check, daemon=True).start()
