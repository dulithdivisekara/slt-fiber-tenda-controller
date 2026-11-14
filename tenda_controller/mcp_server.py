"""
Model Context Protocol (MCP) server for Tenda HG7 GPON ONT Router.

Enables autonomous AI coding agents (Google Antigravity, Claude, Cursor)
to inspect and control the router via structured tools across both
standard 'admin' and ISP 'administrator' (Super Admin) roles.

Author: Dulith Divisekara
"""

import os
import json
from typing import Optional
from mcp.server.mcpserver import MCPServer

from .client import TendaClient
from .exceptions import TendaError

# Initialize MCP server
mcp = MCPServer("tenda-hg7-controller")

DEFAULT_SUPER_USER = os.getenv("TENDA_SUPER_USERNAME", "administrator")
DEFAULT_SUPER_PASS = os.getenv("TENDA_SUPER_PASSWORD", "")


@mcp.tool()
def tenda_get_status(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Get router hardware status, software version, uptime, CPU and memory usage,
    and LAN interface configuration.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            status = client.get_status()
            data = status.model_dump()
            data["role"] = client.role
            return json.dumps(data, indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_optical_power(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Get optical GPON laser telemetry including Rx/Tx optical power (dBm),
    laser temperature, internal voltage, bias current, and ONU registration state (O5).
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            pon = client.get_pon_status()
            data = pon.model_dump()
            data["compliant"] = -28.0 <= pon.rx_power_dbm <= -8.0
            data["description"] = "Normal GPON Class B+ link" if data["compliant"] else "Signal attenuation warning"
            return json.dumps(data, indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_connected_devices(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    List all active client devices connected to the router via Wi-Fi (WLAN) or Ethernet (LAN),
    including hostnames, MAC addresses, and assigned IP addresses.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            devices = client.get_connected_devices()
            return json.dumps([d.model_dump() for d in devices], indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_wifi_config(
    band: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Get current Wi-Fi configuration for a given band ("2.4g" or "5g").
    Returns active SSID, operating channel, and encryption standard.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            cfg = client.get_wifi_config(band)
            return cfg.model_dump_json(indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_set_wifi_config(
    band: str,
    ssid: Optional[str] = None,
    password: Optional[str] = None,
    host: Optional[str] = None,
    username: Optional[str] = None,
    router_password: Optional[str] = None,
) -> str:
    """
    Safely update Wi-Fi network name (SSID) and/or WPA2-PSK passphrase for a band ("2.4g" or "5g").
    Password must be 8-63 characters and cannot contain quotes or backslashes.
    """
    try:
        with TendaClient(host=host, username=username, password=router_password) as client:
            client.set_wifi_config(band=band, ssid=ssid, password=password)
            return json.dumps({
                "status": "success",
                "band": band,
                "ssid_updated": ssid is not None,
                "password_updated": password is not None,
                "message": f"Successfully updated Wi-Fi settings for {band}.",
            }, indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_backup_config(
    destination_path: str = "tenda_backup.xml",
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Export and download the complete raw XML configuration backup from the router.
    Strictly protected against triggering a factory reset.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            dest = client.backup_config(destination_path)
            return json.dumps({
                "status": "success",
                "path": str(dest.resolve()),
                "size_bytes": dest.stat().st_size,
            }, indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_ping(
    target: str,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Execute a diagnostic ICMP ping from the router to an external domain or IP address.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            res = client.ping(target)
            return res.model_dump_json(indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_reboot(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Safely reboot the Tenda HG7 router.
    """
    try:
        with TendaClient(host=host, username=username, password=password) as client:
            client.reboot()
            return json.dumps({
                "status": "success",
                "message": "Reboot command sent. Router is restarting.",
            })
    except TendaError as e:
        return json.dumps({"error": str(e)})


# --- Super Admin MCP Tools ---


@mcp.tool()
def tenda_get_wan_profiles(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Inspect SLT broadband multi-WAN interface profiles and VLANs (VLAN 20 Internet, VLAN 10 Voice, VLAN 30 PeoTV).
    """
    u = username or DEFAULT_SUPER_USER
    p = password or DEFAULT_SUPER_PASS
    if not p:
        return json.dumps({
            "error": "ISP Super Admin password not configured. Set TENDA_SUPER_PASSWORD environment variable or pass password argument."
        })
    try:
        with TendaClient(host=host, username=u, password=p) as client:
            profiles = client.get_wan_profiles()
            return json.dumps([prof.model_dump() for prof in profiles], indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_voip_config(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Inspect SLT Landline VoIP telephony and SIP registrar configuration (Super Admin).
    Returns landline number, SIP proxy, domain, and media ports.
    """
    u = username or DEFAULT_SUPER_USER
    p = password or DEFAULT_SUPER_PASS
    if not p:
        return json.dumps({
            "error": "ISP Super Admin password not configured. Set TENDA_SUPER_PASSWORD environment variable or pass password argument."
        })
    try:
        with TendaClient(host=host, username=u, password=p) as client:
            voip = client.get_voip_config()
            return voip.model_dump_json(indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_acl_rules(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Inspect management service Access Control List (ACL) rules (Super Admin).
    Returns rules for Telnet, SSH, HTTP, HTTPS, SNMP, and ICMP exposure on LAN and WAN.
    """
    u = username or DEFAULT_SUPER_USER
    p = password or DEFAULT_SUPER_PASS
    if not p:
        return json.dumps({
            "error": "ISP Super Admin password not configured. Set TENDA_SUPER_PASSWORD environment variable or pass password argument."
        })
    try:
        with TendaClient(host=host, username=u, password=p) as client:
            rules = client.get_acl_rules()
            return json.dumps([r.model_dump() for r in rules], indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def tenda_get_tr069_config(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Inspect SLT TR-069 Auto-Configuration Server (ACS) settings and periodic inform interval (Super Admin).
    """
    u = username or DEFAULT_SUPER_USER
    p = password or DEFAULT_SUPER_PASS
    if not p:
        return json.dumps({
            "error": "ISP Super Admin password not configured. Set TENDA_SUPER_PASSWORD environment variable or pass password argument."
        })
    try:
        with TendaClient(host=host, username=u, password=p) as client:
            tr069 = client.get_tr069_config()
            return tr069.model_dump_json(indent=2)
    except TendaError as e:
        return json.dumps({"error": str(e)})


def main():
    """Runs the MCP server over standard I/O for AI agent tool calling."""
    mcp.run()


if __name__ == "__main__":
    main()
