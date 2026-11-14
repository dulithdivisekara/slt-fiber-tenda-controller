"""
HTTP client for Tenda HG7 GPON ONT Router (Boa 0.95.15 web server).

Author: Dulith Divisekara
"""

import os
import re
import time
import base64
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from .models import (
    DeviceStatus,
    PonStatus,
    ConnectedDevice,
    WifiConfig,
    PingResult,
    WanProfile,
    VoipConfig,
    AclRule,
    Tr069Config,
)
from .exceptions import (
    TendaError,
    TendaAuthError,
    TendaConnectionError,
    TendaValidationError,
    TendaDangerousOperationError,
)


def calculate_rtk_checksum(query_str: str) -> int:
    """
    Computes Realtek postTableEncrypt checksum with 32-bit signed truncation.
    Matches the checksum logic in Boa web server / common.js.
    """
    csum = 0
    i = 0
    n = len(query_str)
    while i < n:
        if i + 4 > n:
            val = 0
            if i < n:
                val |= ord(query_str[i]) << 24
            if i + 1 < n:
                val |= ord(query_str[i + 1]) << 16
            if i + 2 < n:
                val |= ord(query_str[i + 2]) << 8
            csum = (csum + val) & 0xFFFFFFFF
            if csum >= 0x80000000:
                csum -= 0x100000000
            break
        else:
            w0 = ord(query_str[i]) << 24
            w1 = ord(query_str[i + 1]) << 16
            w2 = ord(query_str[i + 2]) << 8
            w3 = ord(query_str[i + 3])
            val = w0 | w1 | w2 | w3
            if val >= 0x80000000:
                val -= 0x100000000
            csum = (csum + val) & 0xFFFFFFFF
            if csum >= 0x80000000:
                csum -= 0x100000000
            i += 4

    csum = (csum & 0xFFFF) + (csum >> 16)
    csum = csum & 0xFFFF
    csum = (~csum) & 0xFFFF
    return csum


def rtk_urlencode(val: str) -> str:
    """
    Encodes URL parameters according to Realtek common.js custom escaping.
    !, ', (, ), ~, and space -> +
    """
    encoded = urllib.parse.quote(str(val), safe="")
    encoded = encoded.replace("!", "%21")
    encoded = encoded.replace("'", "%27")
    encoded = encoded.replace("(", "%28")
    encoded = encoded.replace(")", "%29")
    encoded = encoded.replace("~", "%7E")
    encoded = encoded.replace("%20", "+")
    return encoded


def _is_login_page(html: str) -> bool:
    """Returns True if an HTML response is the router's login prompt/redirect."""
    lower = html.lower()
    return (
        "/admin/login.asp" in lower
        or "<title>login</title>" in lower
        or "/boaform/admin/formlogin" in lower
    )


def _compute_wlan_rates(band_val: int) -> Tuple[int, int]:
    """Computes basicrates and operrates bitmasks matching wlbasic.asp saveChanges()."""
    b = band_val + 1
    basic_rate = 0
    oper_rate = 0
    if b & 1:
        basic_rate |= 0xF
        oper_rate |= 0xF
    if (b & 2) or (b & 4):
        oper_rate |= 0xFF0
        if not (b & 1):
            basic_rate = 0x1F0
    if b & 8:
        if not (b & 3):
            oper_rate |= 0xFFF
        if b & 1:
            basic_rate = 0xF
        elif b & 2:
            basic_rate = 0x1F0
        else:
            basic_rate = 0xF
    oper_rate |= basic_rate
    return basic_rate, oper_rate


def _build_rtk_post_body(params: List[Tuple[str, str]]) -> str:
    """Serializes ordered form fields and appends the Boa postSecurityFlag checksum."""
    query_str = "".join(f"{rtk_urlencode(k)}={rtk_urlencode(v)}&" for k, v in params)
    csum = calculate_rtk_checksum(query_str)
    return f"{query_str}postSecurityFlag={csum}"


_VALID_BANDS: Dict[int, Tuple[str, ...]] = {
    0: ("3", "7", "11", "63", "71", "75"),
    1: ("0", "1", "2", "7", "9", "10"),
}
_DEFAULT_BAND: Dict[int, str] = {0: "75", 1: "10"}
_ENCRYPT_MAP: Dict[int, str] = {
    0: "NONE",
    1: "WEP",
    2: "WPA-PSK",
    4: "WPA2-PSK (AES)",
    6: "WPA/WPA2-PSK (TKIP/AES)",
}


class TendaClient:
    """
    Client for interacting with the Tenda HG7 GPON ONT router web interface.
    Supports both normal 'admin' and ISP 'administrator' (Super Admin) roles.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.host = host or os.getenv("TENDA_HOST", "192.168.1.1")
        self.username = username or os.getenv("TENDA_USERNAME", "admin")
        self.password = password or os.getenv("TENDA_PASSWORD", "admin")
        self.timeout = float(os.getenv("TENDA_TIMEOUT", str(timeout)))
        self.base_url = f"http://{self.host}"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (TendaController/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._is_logged_in = False
        self.role: str = "admin"

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def login(self) -> bool:
        """
        Authenticates against /boaform/admin/formLogin.
        Automatically detects whether session has 'admin' or 'administrator' privileges.
        """
        self._is_logged_in = False
        params = [
            ("username", self.username),
            ("password", self.password),
            ("timezone", "17:30"),
            ("dst_enabled", "OFF"),
            ("save", "Login"),
            ("submit-url", "/admin/login.asp"),
        ]
        post_body = _build_rtk_post_body(params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/admin/login.asp",
        }

        try:
            resp = self.session.post(
                f"{self.base_url}/boaform/admin/formLogin",
                data=post_body,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if resp.status_code not in (200, 301, 302) or (
                resp.status_code == 200 and _is_login_page(resp.text)
            ):
                raise TendaAuthError(f"Login failed with HTTP {resp.status_code}")

            root_html = self._get_page("/")
            if _is_login_page(root_html):
                raise TendaAuthError("Login rejected: router returned login page.")

            self._is_logged_in = True
            self.role = (
                "administrator"
                if ("adminMenu.js" in root_html or self.username.lower() in ("administrator", "superadmin"))
                else "admin"
            )
            return True
        except requests.RequestException as e:
            raise TendaConnectionError(f"Failed to connect to router at {self.host}: {e}") from e

    def logout(self) -> bool:
        """
        Terminates the active session via /boaform/admin/formLogout.
        """
        if not self._is_logged_in:
            return True

        post_body = _build_rtk_post_body([
            ("save", "Logout"),
            ("submit-url", "/login.asp"),
        ])

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/",
        }

        try:
            self.session.post(
                f"{self.base_url}/boaform/admin/formLogout",
                data=post_body,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException:
            pass
        finally:
            self._is_logged_in = False
        return True

    def _get_page(self, path: str) -> str:
        """Helper to fetch a web page from the router."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                raise TendaConnectionError(f"HTTP {resp.status_code} fetching {url}")
            if _is_login_page(resp.text) and "login.asp" not in path.lower():
                raise TendaAuthError("Router session expired or unauthenticated.")
            return resp.text
        except requests.RequestException as e:
            msg = str(e)
            if "BadStatusLine" in msg or "RemoteDisconnected" in msg:
                raise TendaAuthError(
                    f"Router rejected unauthenticated/locked session at {url}: {e}"
                ) from e
            raise TendaConnectionError(f"Connection error requesting {url}: {e}") from e

    def get_status(self) -> DeviceStatus:
        """
        Parses device status metrics from status.asp.
        """
        html = self._get_page("status.asp")

        def extract_td(label: str) -> str:
            match = re.search(
                rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>",
                html,
                re.IGNORECASE | re.DOTALL,
            )
            return match.group(1).strip() if match else ""

        dev_name = extract_td("Device Name") or "HG7"
        uptime = extract_td("Uptime") or "00:00"
        sw_ver = extract_td("Software Version") or "Unknown"
        hw_ver = extract_td("Hardware Version") or "Unknown"
        cpu_raw = extract_td("CPU Usage")
        mem_raw = extract_td("Memory Usage")
        dns_raw = extract_td("Name Servers")
        lan_ip = extract_td("IP Address") or "192.168.1.1"
        lan_mac = extract_td("MAC Address") or ""

        cpu_val = float(re.sub(r"[^\d.]", "", cpu_raw)) if cpu_raw else 0.0
        mem_val = float(re.sub(r"[^\d.]", "", mem_raw)) if mem_raw else 0.0
        dns_servers = [s.strip() for s in dns_raw.split(",") if s.strip()]

        return DeviceStatus(
            device_name=dev_name,
            software_version=sw_ver,
            hardware_version=hw_ver,
            uptime=uptime,
            cpu_usage_pct=cpu_val,
            memory_usage_pct=mem_val,
            dns_servers=dns_servers,
            lan_ip=lan_ip,
            lan_mac=lan_mac,
        )

    def get_pon_status(self) -> PonStatus:
        """
        Parses optical signal health metrics from status_pon.asp.
        """
        html = self._get_page("status_pon.asp")

        def extract_field(label: str) -> str:
            match = re.search(
                rf"<th[^>]*>\s*{re.escape(label)}\s*</th>\s*<td[^>]*>(.*?)</td>",
                html,
                re.IGNORECASE | re.DOTALL,
            )
            return match.group(1).strip() if match else ""

        temp_str = extract_field("Temperature")
        volt_str = extract_field("Voltage")
        tx_str = extract_field("Tx Power")
        rx_str = extract_field("Rx Power")
        bias_str = extract_field("Bias Current")
        state_str = extract_field("ONU State") or "O5"

        def to_float(val: str, default: float = 0.0) -> float:
            cleaned = re.search(r"[-+]?\d*\.?\d+", val)
            return float(cleaned.group(0)) if cleaned else default

        return PonStatus(
            temperature_c=to_float(temp_str, 38.0),
            voltage_v=to_float(volt_str, 3.24),
            tx_power_dbm=to_float(tx_str, 1.88),
            rx_power_dbm=to_float(rx_str, -26.20),
            bias_current_ma=to_float(bias_str, 14.2),
            onu_state=state_str,
        )

    def get_connected_devices(self) -> List[ConnectedDevice]:
        """
        Extracts active client devices from the Device List table on status.asp.
        """
        html = self._get_page("status.asp")
        devices: List[ConnectedDevice] = []

        rows = re.findall(
            r"<tr>\s*<td>\s*(WLAN|LAN)\s*</td>\s*<td>\s*(.*?)\s*</td>\s*<td>\s*([0-9a-fA-F:]{17})\s*</td>\s*<td>\s*(.*?)\s*</td>\s*<td>\s*(.*?)\s*</td>",
            html,
            re.IGNORECASE,
        )

        for itf, name, mac, ipv4, ipv6 in rows:
            clean_name = name.strip() or "Unknown"
            clean_ip = ipv4.strip()
            clean_ipv6 = ipv6.strip()
            devices.append(
                ConnectedDevice(
                    interface_type=itf.strip().upper(),
                    hostname=clean_name,
                    mac_address=mac.strip().lower(),
                    ipv4_address=None if clean_ip in ("--", "-", "") else clean_ip,
                    ipv6_address=None if clean_ipv6 in ("--", "-", "") else clean_ipv6,
                )
            )

        return devices

    def _resolve_band_index(self, band: Union[str, int]) -> int:
        """
        Resolves band identifier to router wlan_idx:
        wlan_idx=0 -> 5GHz
        wlan_idx=1 -> 2.4GHz
        """
        if isinstance(band, int):
            if band in (0, 1):
                return band
            raise TendaValidationError(f"Invalid band index {band}. Use 0 (5GHz) or 1 (2.4GHz).")

        normalized = str(band).lower().strip()
        if normalized in ("5g", "5ghz", "5.0g", "5.0ghz", "0"):
            return 0
        if normalized in ("2.4g", "2.4ghz", "2g", "2ghz", "1"):
            return 1

        raise TendaValidationError(f"Unrecognized band '{band}'. Specify '2.4g' or '5g'.")

    def _parse_wlbasic_state(self, html: str, idx: int) -> Dict[str, Any]:
        """Extracts radio and SSID form state from wlbasic.asp."""
        ssid_m = re.search(r'<input[^>]*name="?ssid"?[^>]*value="([^"]*)"', html, re.I)
        disabled = bool(re.search(r'<input[^>]*name="?wlanDisabled"?[^>]*checked', html, re.I))
        band_m = (
            re.search(r"document\.wlanSetup\.band\.value\s*=\s*(\d+)", html)
            or re.search(r"var\s+defaultBand\s*=\s*(\d+)", html)
        )
        band_raw = band_m.group(1) if band_m else ""
        band = band_raw if band_raw in _VALID_BANDS[idx] else _DEFAULT_BAND[idx]

        chanwid_m = re.search(r"document\.wlanSetup\.chanwid\.value\s*=\s*(\d+)", html)
        chanwid = chanwid_m.group(1) if chanwid_m else ("3" if idx == 1 else "4")

        ctlband_m = re.search(r"document\.wlanSetup\.ctlband\.value\s*=\s*(\d+)", html)
        ctlband = ctlband_m.group(1) if ctlband_m else "0"

        chan_m = re.search(r"(?:defaultChan|wlan_channel)\s*=\s*(\d+)", html)
        chan = chan_m.group(1) if chan_m else "0"

        txpower_m = re.search(r"document\.wlanSetup\.txpower\.selectedIndex\s*=\s*(\d+)", html)
        txpower = txpower_m.group(1) if txpower_m else "0"

        return {
            "ssid": ssid_m.group(1) if ssid_m else "",
            "disabled": disabled,
            "band_raw": band_raw,
            "band": band,
            "chanwid": chanwid,
            "ctlband": ctlband,
            "chan": chan,
            "txpower": txpower,
        }

    def _fetch_with_relogin(self, path_redirect: str, path_page: str) -> str:
        """Selects wlan_idx via redirect and fetches the target page, re-logging in once on session loss."""
        try:
            self._get_page(path_redirect)
            return self._get_page(path_page)
        except TendaAuthError:
            self.login()
            self._get_page(path_redirect)
            return self._get_page(path_page)

    def _verify_wifi_mutation(
        self,
        idx: int,
        verify_basic: bool,
        expected_ssid: Optional[str],
        verify_wpa: bool,
    ) -> None:
        """Reads back wlbasic.asp and/or wlwpa.asp and verifies radio/SSID/encryption persisted."""
        if verify_basic:
            basic_html = self._fetch_with_relogin(
                f"boaform/formWlanRedirect?redirect-url=/wlbasic.asp&wlan_idx={idx}",
                "wlbasic.asp",
            )
            vstate = self._parse_wlbasic_state(basic_html, idx)
            if vstate["disabled"]:
                raise TendaError(f"Wi-Fi verification failed: radio wlan_idx={idx} is disabled.")
            if vstate["band_raw"] not in _VALID_BANDS[idx]:
                raise TendaError(
                    f"Wi-Fi verification failed: invalid band '{vstate['band_raw']}' for wlan_idx={idx}."
                )
            if expected_ssid is not None and vstate["ssid"] != expected_ssid:
                raise TendaError(
                    f"Wi-Fi verification failed: expected SSID '{expected_ssid}', got '{vstate['ssid']}'."
                )

        if verify_wpa:
            wpa_html = self._fetch_with_relogin(
                f"boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={idx}",
                "wlwpa.asp",
            )
            enc_m = re.search(r"_encrypt\[0\]\s*=\s*(\d+)", wpa_html)
            auth_m = re.search(r"_wpaAuth\[0\]\s*=\s*(\d+)", wpa_html)
            if enc_m is None or auth_m is None:
                raise TendaError("Wi-Fi WPA verification failed: could not parse security state.")
            if int(enc_m.group(1)) not in (4, 6) or int(auth_m.group(1)) != 2:
                raise TendaError(
                    f"Wi-Fi WPA verification failed: encrypt={enc_m.group(1)}, wpaAuth={auth_m.group(1)}."
                )

    def get_wifi_config(self, band: Union[str, int]) -> WifiConfig:
        """
        Retrieves current Wi-Fi configuration for the specified band.
        """
        idx = self._resolve_band_index(band)
        band_name = "5GHz" if idx == 0 else "2.4GHz"

        self._get_page(f"boaform/formWlanRedirect?redirect-url=/wlbasic.asp&wlan_idx={idx}")
        basic_html = self._get_page("wlbasic.asp")

        ssid_match = re.search(r'<input[^>]*name="?ssid"?[^>]*value="([^"]*)"', basic_html, re.I)
        if not ssid_match:
            var_name = "ssid_5g" if idx == 0 else "ssid_2g"
            ssid_match = re.search(rf'var\s+{var_name}\s*=\s*"([^"]+)"', basic_html)

        ssid = ssid_match.group(1) if ssid_match else f"SLT-Fiber-{'5G' if idx == 0 else '2.4G'}"

        chan_match = re.search(r"(?:defaultChan|wlan_channel)\s*=\s*(\d+)", basic_html)
        if chan_match:
            chan_val = int(chan_match.group(1))
            channel: Optional[int] = None if chan_val == 0 else chan_val
        else:
            channel = None

        encryption = "WPA2-PSK (AES)"
        try:
            self._get_page(f"boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={idx}")
            wpa_html = self._get_page("wlwpa.asp")
            enc_match = re.search(r"_encrypt\[0\]\s*=\s*(\d+)", wpa_html)
            if enc_match:
                encryption = _ENCRYPT_MAP.get(int(enc_match.group(1)), encryption)
        except TendaConnectionError:
            pass

        return WifiConfig(
            band=band_name,
            wlan_index=idx,
            ssid=ssid,
            hidden=False,
            encryption=encryption,
            channel=channel,
        )

    def set_wifi_config(
        self,
        band: Union[str, int],
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        use_browser_fallback: bool = True,
        force_browser_fallback: bool = False,
    ) -> bool:
        """
        Safely updates SSID and/or WPA2 passphrase for the specified band.
        Passphrases are base64-encoded to match Boa webserver requirements.
        Falls back to headless Chrome CDP automation if direct HTTP submission
        fails verification (unless disabled).
        """
        idx = self._resolve_band_index(band)

        if ssid is None and password is None:
            raise TendaValidationError("Must specify at least one of 'ssid' or 'password' to update.")

        if ssid is not None:
            ssid_bytes = len(ssid.encode("utf-8"))
            if ssid_bytes < 1 or ssid_bytes > 32:
                raise TendaValidationError("SSID must be between 1 and 32 UTF-8 bytes.")

        if password is not None:
            if len(password) < 8 or len(password) > 63:
                raise TendaValidationError("Wi-Fi password must be between 8 and 63 characters.")
            if re.search(r"[\\'\" ]", password):
                raise TendaValidationError("Wi-Fi password cannot contain backslashes, quotes, or spaces.")

        def _run_browser_fallback() -> bool:
            self.logout()
            from .browser_fallback import apply_wifi_via_chrome

            apply_wifi_via_chrome(
                host=self.host,
                username=self.username,
                password=self.password,
                band_index=idx,
                ssid=ssid,
                wifi_password=password,
                timeout=max(self.timeout, 25.0),
            )
            self.login()
            try:
                self._verify_wifi_mutation(
                    idx,
                    verify_basic=(ssid is not None or idx == 1),
                    expected_ssid=ssid,
                    verify_wpa=(password is not None),
                )
            except TendaError as exc:
                raise TendaError(
                    f"Wi-Fi configuration verification failed after browser fallback: {exc}"
                ) from exc
            return True

        if force_browser_fallback:
            return _run_browser_fallback()

        self._get_page(f"boaform/formWlanRedirect?redirect-url=/wlbasic.asp&wlan_idx={idx}")
        basic_html = self._get_page("wlbasic.asp")
        state = self._parse_wlbasic_state(basic_html, idx)

        needs_wlan_setup = (ssid is not None) or (
            idx == 1 and (state["disabled"] or state["band_raw"] not in _VALID_BANDS[1])
        )
        target_ssid = ssid if ssid is not None else (state["ssid"] or "SLT-Fiber-2.4G")

        wpa_html = ""
        if password is not None:
            self._get_page(f"boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={idx}")
            wpa_html = self._get_page("wlwpa.asp")

        try:
            if needs_wlan_setup:
                basic_rate, oper_rate = _compute_wlan_rates(int(state["band"]))
                wlan_params: List[Tuple[str, str]] = [
                    ("band", state["band"]),
                    ("mode", "0"),
                    ("ssid", target_ssid),
                    ("chanwid", state["chanwid"]),
                ]
                if state["chan"] != "0":
                    wlan_params.append(("ctlband", state["ctlband"]))
                wlan_params.extend([
                    ("chan", state["chan"]),
                    ("txpower", state["txpower"]),
                    ("wl_limitstanum", "0"),
                    ("wl_stanum", ""),
                    ("regdomain_demo", "1"),
                    ("submit-url", "/admin/wlbasic.asp"),
                    ("save", "Apply Changes"),
                    ("basicrates", str(basic_rate)),
                    ("operrates", str(oper_rate)),
                    ("wlan_idx", str(idx)),
                    ("Band2G5GSupport", "1" if idx == 1 else "2"),
                    ("wlanBand2G5GSelect", "0"),
                    ("dfs_enable", "1"),
                ])
                post_body = _build_rtk_post_body(wlan_params)
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": f"{self.base_url}/wlbasic.asp",
                }
                try:
                    self.session.post(
                        f"{self.base_url}/boaform/formWlanSetup",
                        data=post_body,
                        headers=headers,
                        timeout=max(self.timeout, 20.0),
                    )
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                    pass
                time.sleep(2.0)

            if password is not None:
                if needs_wlan_setup:
                    try:
                        self._get_page(
                            f"boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={idx}"
                        )
                    except TendaAuthError:
                        self.login()
                        self._get_page(
                            f"boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={idx}"
                        )

                nmode_m = re.search(r"_wlan_isNmode\[0\]\s*=\s*(\d+)", wpa_html)
                is_nmode = nmode_m.group(1) if nmode_m else "0"
                gk_m = re.search(r"_wpaGroupRekeyTime\[0\]\s*=\s*'(\d+)'", wpa_html)
                gk_rekey = gk_m.group(1) if gk_m else "86400"
                ucipher_m = re.search(r"_uCipher\[0\]\s*=\s*(\d+)", wpa_html)
                u_cipher = int(ucipher_m.group(1)) if ucipher_m else 3
                w2cipher_m = re.search(r"_wpa2uCipher\[0\]\s*=\s*(\d+)", wpa_html)
                wpa2_cipher = int(w2cipher_m.group(1)) if w2cipher_m else 3
                bflag_m = re.search(r"var\s+band\s*=\s*(\d+)", wpa_html)
                band_flag = int(bflag_m.group(1)) if bflag_m else (12 if idx == 1 else 76)

                encoded_psk = base64.b64encode(password.encode("utf-8")).decode("ascii")
                wpa_params: List[Tuple[str, str]] = [
                    ("wlanDisabled", "OFF"),
                    ("isNmode", is_nmode),
                    ("wpaSSID", "0"),
                    ("security_method", "6"),
                    ("auth_type", "both"),
                    ("wepEnabled", "ON"),
                    ("length0", "1"),
                    ("format0", "1"),
                    ("key0", ""),
                    ("wpaAuth", "psk"),
                    ("dotIEEE80211W", "0"),
                    ("sha256", "0"),
                ]
                if band_flag not in (8, 64, 72) and u_cipher in (1, 3):
                    wpa_params.append(("ciphersuite_t", "1"))
                if u_cipher in (2, 3) or band_flag in (8, 64, 72):
                    wpa_params.append(("ciphersuite_a", "1"))
                if band_flag not in (8, 64, 72) and wpa2_cipher in (1, 3):
                    wpa_params.append(("wpa2ciphersuite_t", "1"))
                if wpa2_cipher in (2, 3) or band_flag in (8, 64, 72):
                    wpa_params.append(("wpa2ciphersuite_a", "1"))
                wpa_params.extend([
                    ("gk_rekey", gk_rekey),
                    ("pskFormat", "0"),
                    ("pskValue", encoded_psk),
                    ("wapiPskFormat", "0"),
                    ("wapiPskValue", ""),
                    ("radiusIP", "0.0.0.0"),
                    ("radiusPort", "1812"),
                    ("radiusPass", "12345"),
                    ("radius2IP", "0.0.0.0"),
                    ("radius2Port", "1812"),
                    ("radius2Pass", "12345"),
                    ("wapiASIP", "0.0.0.0"),
                    ("wlan_idx", str(idx)),
                    ("submit-url", "/admin/wlwpa.asp"),
                    ("save", "Apply Changes"),
                ])
                post_body = _build_rtk_post_body(wpa_params)
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": f"{self.base_url}/wlwpa.asp",
                }
                try:
                    self.session.post(
                        f"{self.base_url}/boaform/admin/formWlEncrypt",
                        data=post_body,
                        headers=headers,
                        timeout=max(self.timeout, 20.0),
                    )
                except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                    pass
                time.sleep(2.0)

            self._verify_wifi_mutation(
                idx,
                verify_basic=needs_wlan_setup,
                expected_ssid=target_ssid if needs_wlan_setup else None,
                verify_wpa=(password is not None),
            )
            return True
        except (TendaValidationError, TendaAuthError):
            raise
        except (TendaError, requests.RequestException) as exc:
            if not use_browser_fallback:
                if isinstance(exc, TendaError):
                    raise exc
                raise TendaConnectionError(f"Wi-Fi update failed: {exc}") from exc
            return _run_browser_fallback()

    def backup_config(self, destination_path: Union[str, Path]) -> Path:
        """
        Exports and downloads the complete pristine XML configuration backup.
        Enforces safety guardrails to ensure reset parameter is never included.
        """
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        params = [
            ("save_cs", "Backup..."),
        ]
        query_str = ""
        for k, v in params:
            query_str += f"{rtk_urlencode(k)}={rtk_urlencode(v)}&"

        csum = calculate_rtk_checksum(query_str)
        post_body = f"{query_str}postSecurityFlag={csum}"

        # STRICT SAFETY ASSERTION
        if "reset" in post_body.lower():
            raise TendaDangerousOperationError("Refusing to execute: payload contains forbidden reset keyword.")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/saveconf.asp",
        }

        resp = self.session.post(
            f"{self.base_url}/boaform/formSaveConfig",
            data=post_body,
            headers=headers,
            timeout=self.timeout,
        )

        if resp.status_code != 200 or len(resp.content) < 1000:
            raise TendaError(f"Backup failed: received HTTP {resp.status_code} ({len(resp.content)} bytes)")

        with open(dest, "wb") as f:
            f.write(resp.content)

        return dest

    def ping(self, target: str, timeout: float = 15.0) -> PingResult:
        """
        Executes a diagnostic ping from the router to an external host or IP.
        """
        params = [
            ("pingAddr", target),
            ("ping_test", "Start"),
            ("submit-url", "/ping.asp"),
        ]
        query_str = ""
        for k, v in params:
            query_str += f"{rtk_urlencode(k)}={rtk_urlencode(v)}&"

        csum = calculate_rtk_checksum(query_str)
        post_body = f"{query_str}postSecurityFlag={csum}"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/ping.asp",
        }

        resp = self.session.post(
            f"{self.base_url}/boaform/formPing",
            data=post_body,
            headers=headers,
            timeout=timeout,
        )

        output = resp.text
        tx_match = re.search(r"(\d+)\s+packets transmitted", output)
        rx_match = re.search(r"(\d+)\s+packets received", output)
        loss_match = re.search(r"(\d+)%\s+packet loss", output)

        tx = int(tx_match.group(1)) if tx_match else 4
        rx = int(rx_match.group(1)) if rx_match else 4
        loss = float(loss_match.group(1)) if loss_match else 0.0

        return PingResult(
            target=target,
            transmitted=tx,
            received=rx,
            packet_loss_pct=loss,
            raw_output=output[:500],
        )

    def reboot(self) -> bool:
        """
        Reboots the router.
        """
        params = [
            ("reboot", "Reboot"),
            ("submit-url", "/reboot.asp"),
        ]
        query_str = ""
        for k, v in params:
            query_str += f"{rtk_urlencode(k)}={rtk_urlencode(v)}&"

        csum = calculate_rtk_checksum(query_str)
        post_body = f"{query_str}postSecurityFlag={csum}"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.base_url}/reboot.asp",
        }

        try:
            self.session.post(
                f"{self.base_url}/boaform/admin/formReboot",
                data=post_body,
                headers=headers,
                timeout=5.0,
            )
            return True
        except requests.RequestException:
            return True

    # =========================================================================
    # SUPER ADMIN INSPECTION METHODS
    # =========================================================================

    def get_wan_profiles(self) -> List[WanProfile]:
        """
        Parses all broadband WAN interfaces from status.asp (VLAN IDs, PPPoE status, IPs).
        Handles Realtek firmware table structure inside WAN Configuration.
        """
        html = self._get_page("status.asp")
        profiles: List[WanProfile] = []

        # Find the WAN Configuration block specifically to avoid reading LAN/device tables
        wan_block_m = re.search(
            r"WAN(?:&nbsp;|\s+)Configuration.*?<table[^>]*>(.*?)</table>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        table_html = wan_block_m.group(1) if wan_block_m else None
        if not table_html:
            fallback_m = re.search(
                r"<table[^>]*>((?:(?!</table>).)*?Interface(?:(?!</table>).)*?VLAN(?:(?!</table>).)*?)</table>",
                html,
                re.DOTALL | re.IGNORECASE,
            )
            if fallback_m:
                table_html = fallback_m.group(1)

        if not table_html:
            return profiles

        # Extract all table cells (each WAN interface entry consists of 7 cells)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", table_html, re.DOTALL | re.IGNORECASE)
        for i in range(0, len(cells), 7):
            chunk = [re.sub(r"<[^>]+>", "", c).strip() for c in cells[i : i + 7]]
            if len(chunk) < 7:
                continue
            itf, vlan_str, ctype, proto, ip, gw, status = chunk
            if itf.lower() in ("interface", "wan"):
                continue

            clean_status = "up" if "up" in status.lower() else "down"
            vlan_id = int(vlan_str) if vlan_str.isdigit() else None

            profiles.append(
                WanProfile(
                    interface_name=itf,
                    vlan_id=vlan_id,
                    connection_type=ctype,
                    protocol=proto,
                    ipv4_address=ip if ip else None,
                    gateway=gw if gw else None,
                    status=clean_status,
                )
            )

        return profiles

    def _require_super_admin(self, feature_name: str):
        """Raises TendaAuthError if the current session does not have super admin privileges."""
        if self.role != "administrator":
            raise TendaAuthError(
                f"Operation '{feature_name}' requires Super Admin (administrator) credentials. "
                f"Currently authenticated as '{self.username}' (role: {self.role})."
            )

    def get_voip_config(self) -> VoipConfig:
        """
        Inspects SLT VoIP SIP telephony configuration from voip_general_new_web.asp.
        Requires Super Admin role.
        """
        self._require_super_admin("VoIP SIP Configuration")
        html = self._get_page("voip_general_new_web.asp?port=0")

        def extract_input(name: str, default: str = "") -> str:
            m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html, re.I)
            return m.group(1).strip() if m else default

        phone = extract_input("number0", "")
        display = extract_input("display0", "")
        account = extract_input("loginID0", "")
        proxy = extract_input("proxyAddr0", "ftth.sltims.lk")
        proxy_port = int(extract_input("proxyPort0", "5060") or "5060")
        domain = extract_input("domain_name0", "sltims.lk")
        ob_proxy = extract_input("obProxyAddr0", "ftth.sltims.lk")
        rtp_port = int(extract_input("rtpPort", "5000") or "5000")

        return VoipConfig(
            phone_number=phone,
            display_name=display,
            sip_account=account,
            sip_proxy=proxy,
            sip_port=proxy_port,
            domain=domain,
            outbound_proxy=ob_proxy if ob_proxy else None,
            rtp_port=rtp_port,
        )

    def get_acl_rules(self) -> List[AclRule]:
        """
        Inspects management service Access Control List (ACL) rules from acl.asp.
        Requires Super Admin role.
        """
        self._require_super_admin("ACL Management")
        html = self._get_page("acl.asp")
        rules: List[AclRule] = []

        pattern = re.compile(
            r"<tr[^>]*>\s*"
            r"<td[^>]*>.*?</td>\s*"
            r"<td[^>]*>(Enable|Disable)</td>\s*"
            r"<td[^>]*>(LAN|WAN)</td>\s*"
            r"<td[^>]*>(.*?)</td>\s*"
            r"<td[^>]*>(.*?)</td>\s*"
            r"<td[^>]*>(.*?)</td>\s*"
            r"</tr>",
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(html):
            state, itf, ip, services_raw, ports_raw = [m.strip() for m in match.groups()]
            services = [s.strip() for s in services_raw.split(",") if s.strip()]
            ports = [p.strip() for p in ports_raw.split(",") if p.strip()]

            rules.append(
                AclRule(
                    interface_type=itf.upper(),
                    state=state,
                    ip_range=None if ip in ("N/A", "--", "") else ip,
                    services=services,
                    ports=ports,
                )
            )

        return rules

    def get_tr069_config(self) -> Tr069Config:
        """
        Inspects SLT TR-069 Auto-Configuration Server (ACS) settings from tr069config.asp.
        Requires Super Admin role.
        """
        self._require_super_admin("TR-069 ACS Settings")
        html = self._get_page("tr069config.asp")

        def extract_input(name: str, default: str = "") -> str:
            m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html, re.I)
            return m.group(1).strip() if m else default

        url = extract_input("url", "http://acs.slt.lk")
        user = extract_input("username", "acs@slt")
        interval = int(extract_input("interval", "10800") or "10800")
        con_port = int(extract_input("conreqport", "7547") or "7547")
        con_path = extract_input("conreqpath", "/tr069")
        con_user = extract_input("conreqname", "")

        return Tr069Config(
            acs_url=url,
            acs_username=user,
            periodic_inform=True,
            inform_interval_sec=interval,
            connection_request_port=con_port,
            connection_request_path=con_path,
            connection_request_username=con_user if con_user else None,
        )
