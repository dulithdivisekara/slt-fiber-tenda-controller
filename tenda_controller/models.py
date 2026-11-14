"""
Pydantic data models for Tenda HG7 telemetry and configuration.

Author: Dulith Divisekara
"""

from typing import Optional, List
from pydantic import BaseModel, field_validator


class DeviceStatus(BaseModel):
    """Router hardware and operating metrics from status.asp."""
    device_name: str = "HG7"
    software_version: str
    hardware_version: str
    uptime: str
    cpu_usage_pct: float
    memory_usage_pct: float
    dns_servers: List[str]
    lan_ip: str
    lan_mac: str


class PonStatus(BaseModel):
    """Optical laser health metrics from status_pon.asp."""
    temperature_c: float
    voltage_v: float
    tx_power_dbm: float
    rx_power_dbm: float
    bias_current_ma: float
    onu_state: str  # e.g., "O5" (Operational)


class ConnectedDevice(BaseModel):
    """A client device connected to LAN or WLAN."""
    interface_type: str  # "WLAN" or "LAN"
    hostname: str
    mac_address: str
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None

    @field_validator("ipv4_address", mode="before")
    def clean_ipv4(cls, v):
        if not v or str(v).strip() in ("--", "-", "None", ""):
            return None
        return str(v).strip()

    @field_validator("ipv6_address", mode="before")
    def clean_ipv6(cls, v):
        if not v or str(v).strip() in ("--", "-", "None", ""):
            return None
        return str(v).strip()


class WifiConfig(BaseModel):
    """Wireless network settings for a frequency band."""
    band: str  # "2.4GHz" or "5GHz"
    wlan_index: int  # 0 for 5GHz, 1 for 2.4GHz
    ssid: str
    hidden: bool = False
    encryption: str = "WPA2-PSK (AES)"
    channel: Optional[int] = None


class PingResult(BaseModel):
    """ICMP diagnostic ping execution results."""
    target: str
    transmitted: int
    received: int
    packet_loss_pct: float
    min_rtt_ms: Optional[float] = None
    avg_rtt_ms: Optional[float] = None
    max_rtt_ms: Optional[float] = None
    raw_output: str


# --- Super Admin Models ---


class WanProfile(BaseModel):
    """Broadband WAN interface connection profile from status.asp / multi_wan_generic.asp."""
    interface_name: str  # e.g., "ppp0_nas0_0", "nas0_1", "nas0_2"
    vlan_id: Optional[int] = None  # e.g., 20, 10, 30
    connection_type: str  # e.g., "INTERNET_TR069", "VOICE", "Other"
    protocol: str  # e.g., "PPPoE", "IPoE", "Bridged"
    ipv4_address: Optional[str] = None
    gateway: Optional[str] = None
    status: str  # e.g., "up"


class VoipConfig(BaseModel):
    """Voice over IP (VoIP) telephony SIP configuration from voip_general_new_web.asp."""
    phone_number: str  # e.g., "+94112000000"
    display_name: str  # e.g., "0112000000"
    sip_account: str  # e.g., "+94112000000F0@sltims.lk"
    sip_proxy: str  # e.g., "ftth.sltims.lk"
    sip_port: int = 5060
    domain: str  # e.g., "sltims.lk"
    outbound_proxy: Optional[str] = None
    rtp_port: int = 5000


class AclRule(BaseModel):
    """Access Control List rule for management service exposure from acl.asp."""
    interface_type: str  # "LAN" or "WAN"
    state: str  # "Enable" or "Disable"
    ip_range: Optional[str] = None  # e.g., "222.165.185.1-222.165.185.6" or "N/A"
    services: List[str]  # e.g., ["ftp", "web", "https", "snmp", "ping"]
    ports: List[str]  # e.g., ["21", "80", "443", "161", "162", "--"]


class Tr069Config(BaseModel):
    """TR-069 CPE WAN Management Protocol (CWMP) configuration from tr069config.asp."""
    acs_url: str  # e.g., "http://acs.slt.lk"
    acs_username: str  # e.g., "acs@slt"
    periodic_inform: bool = True
    inform_interval_sec: int  # e.g., 10800
    connection_request_port: int = 7547
    connection_request_path: str = "/tr069"
    connection_request_username: Optional[str] = None
