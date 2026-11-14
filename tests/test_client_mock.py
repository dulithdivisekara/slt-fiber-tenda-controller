"""
Mock integration tests for TendaClient parsing and validation.
"""

import base64
import unittest
import urllib.parse
from unittest.mock import MagicMock, patch
from tenda_controller.client import TendaClient, calculate_rtk_checksum
from tenda_controller.exceptions import (
    TendaAuthError,
    TendaConnectionError,
    TendaDangerousOperationError,
    TendaError,
    TendaValidationError,
)


SAMPLE_STATUS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Device Status</title></head>
<body>
<table>
<tr><th width=40%>Device Name</th><td width=60%>HG7</td></tr>
<tr><th width=40%>Uptime</th><td width=60%>18:22</td></tr>
<tr><th width=40%>Software Version</th><td width=60%>v1.0.17</td></tr>
<tr><th width=40%>Hardware Version</th><td width=60%>v2.0</td></tr>
<tr><th width=40%>CPU Usage</th><td width=60%>2%</td></tr>
<tr><th width=40%>Memory Usage</th><td width=60%>27%</td></tr>
<tr><th width=40%>Name Servers</th><td width=60%>222.165.171.2, 222.165.171.1</td></tr>
<tr><th width=40%>IP Address</th><td width=60%>192.168.1.1</td></tr>
<tr><th width=40%>MAC Address</th><td width="60%">502b73000000</td></tr>
</table>
<table>
<tr><td>WLAN</td><td>client-workstation</td><td>AA:BB:CC:DD:EE:FF</td><td>192.168.1.4</td><td>fe80::1</td></tr>
<tr><td>LAN</td><td>android-device</td><td>00:00:5E:00:53:02</td><td>--</td><td>fe80::2</td></tr>
</table>
</body>
</html>
"""

SAMPLE_PON_HTML = """
<!DOCTYPE html>
<html>
<head><title>PON Status</title></head>
<body>
<table>
<tr><th width=40%>Temperature</th><td width=60%>38.378906 C</td></tr>
<tr><th width=40%>Voltage</th><td width=60%>3.237000 V</td></tr>
<tr><th width=40%>Tx Power</th><td width=60%>1.876936  dBm</td></tr>
<tr><th width=40%>Rx Power</th><td width=60%>-26.197887  dBm</td></tr>
<tr><th width=40%>Bias Current</th><td width=60%>14.200000 mA</td></tr>
<tr><th width="40%">ONU State</th><td width="60%">O5</td></tr>
</table>
</body>
</html>
"""


class TestClientMock(unittest.TestCase):
    def setUp(self):
        self.client = TendaClient(host="192.168.1.1")

    @patch.object(TendaClient, "_get_page")
    def test_get_status_parsing(self, mock_get):
        mock_get.return_value = SAMPLE_STATUS_HTML
        status = self.client.get_status()

        self.assertEqual(status.device_name, "HG7")
        self.assertEqual(status.software_version, "v1.0.17")
        self.assertEqual(status.hardware_version, "v2.0")
        self.assertEqual(status.uptime, "18:22")
        self.assertEqual(status.cpu_usage_pct, 2.0)
        self.assertEqual(status.memory_usage_pct, 27.0)
        self.assertEqual(status.lan_ip, "192.168.1.1")
        self.assertIn("222.165.171.2", status.dns_servers)

    @patch.object(TendaClient, "_get_page")
    def test_get_pon_status_parsing(self, mock_get):
        mock_get.return_value = SAMPLE_PON_HTML
        pon = self.client.get_pon_status()

        self.assertAlmostEqual(pon.temperature_c, 38.378906)
        self.assertAlmostEqual(pon.voltage_v, 3.237)
        self.assertAlmostEqual(pon.tx_power_dbm, 1.876936)
        self.assertAlmostEqual(pon.rx_power_dbm, -26.197887)
        self.assertEqual(pon.onu_state, "O5")

    @patch.object(TendaClient, "_get_page")
    def test_connected_devices_null_ip_handling(self, mock_get):
        mock_get.return_value = SAMPLE_STATUS_HTML
        devices = self.client.get_connected_devices()

        self.assertEqual(len(devices), 2)
        dev1 = devices[0]
        self.assertEqual(dev1.hostname, "client-workstation")
        self.assertEqual(dev1.ipv4_address, "192.168.1.4")

        dev2 = devices[1]
        self.assertEqual(dev2.hostname, "android-device")
        self.assertIsNone(dev2.ipv4_address, "Expected '--' to be parsed as None")

    def test_wifi_password_validation(self):
        # Short password
        with self.assertRaises(TendaValidationError):
            self.client.set_wifi_config("2.4g", password="short")

        # Forbidden characters (backslash, quotes, spaces)
        with self.assertRaises(TendaValidationError):
            self.client.set_wifi_config("2.4g", password='pass"with"quote')
        with self.assertRaises(TendaValidationError):
            self.client.set_wifi_config("2.4g", password="pass\\with\\slash")
        with self.assertRaises(TendaValidationError):
            self.client.set_wifi_config("2.4g", password="pass with space")

    def test_band_resolution(self):
        self.assertEqual(self.client._resolve_band_index("5g"), 0)
        self.assertEqual(self.client._resolve_band_index("5GHz"), 0)
        self.assertEqual(self.client._resolve_band_index("2.4g"), 1)
        self.assertEqual(self.client._resolve_band_index("2.4GHz"), 1)
        with self.assertRaises(TendaValidationError):
            self.client._resolve_band_index("6g")

    def test_login_rejects_login_page_html(self):
        login_html = "<html><head><title>Login</title></head><script>top.location.href='/admin/login.asp'</script></html>"
        post_resp = MagicMock(status_code=200, text=login_html)
        with patch.object(self.client.session, "post", return_value=post_resp):
            with self.assertRaises(TendaAuthError):
                self.client.login()
        self.assertFalse(self.client._is_logged_in)

    def test_get_wifi_config_parses_default_chan_and_encryption(self):
        basic_html = """
        <script>defaultChan = 0;</script>
        <input type="text" name="ssid" value="TestNet-2.4G">
        """
        wpa_html = """
        <script>_encrypt[0] = 6; _wpaAuth[0] = 2;</script>
        """
        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", basic_html, "", wpa_html],
        ):
            cfg = self.client.get_wifi_config("2.4g")
        self.assertEqual(cfg.ssid, "TestNet-2.4G")
        self.assertIsNone(cfg.channel)
        self.assertEqual(cfg.encryption, "WPA/WPA2-PSK (TKIP/AES)")

        # Falls back to default encryption on TendaConnectionError fetching wlwpa.asp
        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", basic_html, TendaConnectionError("timeout")],
        ):
            cfg_fallback = self.client.get_wifi_config("2.4g")
        self.assertEqual(cfg_fallback.encryption, "WPA2-PSK (AES)")

        # Never swallows TendaAuthError fetching wlwpa.asp
        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", basic_html, TendaAuthError("expired")],
        ):
            with self.assertRaises(TendaAuthError):
                self.client.get_wifi_config("2.4g")

    def test_set_wifi_config_24g_payload(self):
        pre_basic = """
        <script>
        defaultChan = 0;
        document.wlanSetup.band.value = 11;
        document.wlanSetup.chanwid.value = 3;
        document.wlanSetup.ctlband.value = 0;
        document.wlanSetup.txpower.selectedIndex = 0;
        </script>
        <input type="text" name="ssid" value="OldSSID">
        """
        pre_wpa = """
        <script>
        var band = 12;
        _wlan_isNmode[0] = 0;
        _wpaGroupRekeyTime[0] = '86400';
        _uCipher[0] = 3;
        _wpa2uCipher[0] = 3;
        </script>
        """
        post_basic = """
        <script>
        defaultChan = 0;
        document.wlanSetup.band.value = 10;
        </script>
        <input type="text" name="ssid" value="TestNet-2.4G">
        """
        post_wpa = "<script>_encrypt[0] = 6; _wpaAuth[0] = 2;</script>"

        posted = []

        def fake_post(url, data=None, headers=None, timeout=None):
            posted.append((url, data))
            return MagicMock(status_code=200, text="ok")

        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", pre_basic, "", pre_wpa, "", "", post_basic, "", post_wpa],
        ), patch.object(self.client.session, "post", side_effect=fake_post), patch(
            "tenda_controller.client.time.sleep"
        ):
            ok = self.client.set_wifi_config("2.4g", ssid="TestNet-2.4G", password="MockPass@2026")

        self.assertTrue(ok)
        self.assertEqual(len(posted), 2)

        setup_url, setup_body = posted[0]
        self.assertTrue(setup_url.endswith("/boaform/formWlanSetup"))
        setup_prefix, setup_csum_part = setup_body.rsplit("postSecurityFlag=", 1)
        self.assertEqual(int(setup_csum_part), calculate_rtk_checksum(setup_prefix))
        setup_kv = dict(urllib.parse.parse_qsl(setup_prefix, keep_blank_values=True))
        self.assertEqual(setup_kv["band"], "10")
        self.assertEqual(setup_kv["Band2G5GSupport"], "1")
        self.assertEqual(setup_kv["basicrates"], "15")
        self.assertEqual(setup_kv["operrates"], "4095")
        self.assertEqual(setup_kv["submit-url"], "/admin/wlbasic.asp")
        self.assertNotIn("wlanDisabled", setup_kv)
        self.assertNotIn("ctlband", setup_kv)

        enc_url, enc_body = posted[1]
        self.assertTrue(enc_url.endswith("/boaform/admin/formWlEncrypt"))
        enc_prefix, enc_csum_part = enc_body.rsplit("postSecurityFlag=", 1)
        self.assertEqual(int(enc_csum_part), calculate_rtk_checksum(enc_prefix))
        enc_kv = dict(urllib.parse.parse_qsl(enc_prefix, keep_blank_values=True))
        self.assertEqual(enc_kv["security_method"], "6")
        self.assertEqual(enc_kv["wpaAuth"], "psk")
        self.assertEqual(enc_kv["wpaSSID"], "0")
        self.assertEqual(enc_kv["pskFormat"], "0")
        self.assertEqual(enc_kv["pskValue"], base64.b64encode(b"MockPass@2026").decode("ascii"))
        self.assertEqual(enc_kv["submit-url"], "/admin/wlwpa.asp")

    def test_set_wifi_config_5g_payload(self):
        pre_basic = """
        <script>
        defaultChan = 0;
        document.wlanSetup.band.value = 75;
        document.wlanSetup.chanwid.value = 4;
        document.wlanSetup.txpower.selectedIndex = 0;
        </script>
        <input type="text" name="ssid" value="SLT-Fiber-5G_0000">
        """
        post_basic = """
        <script>defaultChan = 0; document.wlanSetup.band.value = 75;</script>
        <input type="text" name="ssid" value="TestNet-5G">
        """
        posted = []

        def fake_post(url, data=None, headers=None, timeout=None):
            posted.append((url, data))
            return MagicMock(status_code=200, text="ok")

        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", pre_basic, "", post_basic],
        ), patch.object(self.client.session, "post", side_effect=fake_post), patch(
            "tenda_controller.client.time.sleep"
        ):
            ok = self.client.set_wifi_config("5g", ssid="TestNet-5G")

        self.assertTrue(ok)
        setup_kv = dict(urllib.parse.parse_qsl(posted[0][1], keep_blank_values=True))
        self.assertEqual(setup_kv["band"], "75")
        self.assertEqual(setup_kv["Band2G5GSupport"], "2")
        self.assertEqual(setup_kv["wlan_idx"], "0")

    def test_set_wifi_config_fallback_on_verification_failure(self):
        pre_basic = '<script>defaultChan = 0; document.wlanSetup.band.value = 10;</script><input name="ssid" value="Old">'
        stale_basic = '<script>defaultChan = 0; document.wlanSetup.band.value = 10;</script><input name="ssid" value="Old">'
        updated_basic = '<script>defaultChan = 0; document.wlanSetup.band.value = 10;</script><input name="ssid" value="TestNet-2.4G">'
        call_order = []

        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", pre_basic, "", stale_basic, "", updated_basic],
        ), patch.object(self.client.session, "post", return_value=MagicMock(status_code=200)), patch.object(
            self.client, "logout", side_effect=lambda: call_order.append("logout") or True
        ), patch.object(
            self.client, "login", side_effect=lambda: call_order.append("login") or True
        ), patch(
            "tenda_controller.browser_fallback.apply_wifi_via_chrome",
            side_effect=lambda **kw: call_order.append("chrome") or True,
        ), patch("tenda_controller.client.time.sleep"):
            ok = self.client.set_wifi_config("2.4g", ssid="TestNet-2.4G")

        self.assertTrue(ok)
        self.assertEqual(call_order, ["logout", "chrome", "login"])

    def test_set_wifi_config_no_fallback_raises(self):
        pre_basic = "<script>defaultChan = 0; document.wlanSetup.band.value = 10;</script><input name='ssid' value='Old'>"
        stale_basic = "<script>defaultChan = 0; document.wlanSetup.band.value = 10;</script><input name='ssid' value='Old'>"

        with patch.object(
            self.client,
            "_get_page",
            side_effect=["", pre_basic, "", stale_basic],
        ), patch.object(self.client.session, "post", return_value=MagicMock(status_code=200)), patch(
            "tenda_controller.client.time.sleep"
        ):
            with self.assertRaises(TendaError):
                self.client.set_wifi_config(
                    "2.4g", ssid="TestNet-2.4G", use_browser_fallback=False
                )

    def test_set_wifi_config_auth_error_skips_fallback(self):
        with patch.object(
            self.client,
            "_get_page",
            side_effect=TendaAuthError("bad creds"),
        ), patch("tenda_controller.browser_fallback.apply_wifi_via_chrome") as mock_chrome:
            with self.assertRaises(TendaAuthError):
                self.client.set_wifi_config("2.4g", ssid="TestNet-2.4G")
        mock_chrome.assert_not_called()


if __name__ == "__main__":
    unittest.main()
