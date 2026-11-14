"""
Mock integration tests for TendaClient parsing and validation.
"""

import unittest
from unittest.mock import MagicMock, patch
from tenda_controller.client import TendaClient
from tenda_controller.exceptions import TendaValidationError, TendaDangerousOperationError


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


if __name__ == "__main__":
    unittest.main()
