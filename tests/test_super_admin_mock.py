"""
Mock integration tests for Super Admin features (WAN, VoIP, ACL, TR-069).
"""

import json
import unittest
from unittest.mock import patch
from tenda_controller.client import TendaClient
from tenda_controller.exceptions import TendaAuthError
from tenda_controller.mcp_server import tenda_get_wan_profiles, tenda_get_voip_config

SAMPLE_STATUS_WAN_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="column_title">
<p>WAN&nbsp;Configuration</p>
</div>
<table>
<tr>
<th width="8%" align=center>Interface</th>
<th width="12%" align=center>VLAN ID</th>
<th width="12%" align=center>Connection Type</th>
<th width="12%" align=center>Protocol</th>
<th width="22%" align=center>IP Address</th>
<th width="22%" align=center>Gateway</th>
<th width="12%" align=center>Status</th>
</tr>
<tr>
<td align=center width="5%">ppp0_nas0_0</td>
<td align=center width="1%">20</td>
<td align=center width="9%">INTERNET_TR069</td>
<td align=center width="5%">PPPoE</td>
<td align=center width="10%">100.64.0.1</td>
<td align=center width="10%">100.64.0.254</td>
<td align=center width="23%">up 06:17:53 / 18:20:35</td>
</tr>
<tr>
<td align=center width="5%">nas0_1</td>
<td align=center width="1%">10</td>
<td align=center width="9%">VOICE</td>
<td align=center width="5%">IPoE</td>
<td align=center width="10%">192.0.2.10</td>
<td align=center width="10%">192.0.2.1</td>
<td align=center width="23%">up</td>
</tr>
<tr>
<td align=center width="5%">nas0_2</td>
<td align=center width="1%">30</td>
<td align=center width="9%">Other</td>
<td align=center width="5%">Bridged</td>
<td align=center width="10%"></td>
<td align=center width="10%"></td>
<td align=center width="23%">up</td>
</tr>
</table>
</body>
</html>
"""

SAMPLE_VOIP_HTML = """
<!DOCTYPE html>
<html>
<body>
<input type="text" name="display0" value="0112345678">
<input type="text" name="number0" value="+94112345678">
<input type="text" name="loginID0" value="+94112345678F0@sltims.lk">
<input type="text" name="proxyAddr0" value="ftth.sltims.lk">
<input type="text" name="proxyPort0" value="5060">
<input type="text" name="domain_name0" value="sltims.lk">
<input type="text" name="obProxyAddr0" value="ftth.sltims.lk">
<input type="text" name="rtpPort" value="5000">
</body>
</html>
"""

SAMPLE_ACL_HTML = """
<!DOCTYPE html>
<html>
<body>
<table>
<tr>
<th>Select</th><th>State</th><th>Interface</th><th>IP Address</th><th>Service Name</th><th>Port</th>
</tr>
<tr>
<td><input type="checkbox"></td>
<td>Enable</td>
<td>LAN</td>
<td>N/A</td>
<td>ftp,web,https,snmp,ping</td>
<td>21,80,443,161,162,--</td>
</tr>
<tr>
<td><input type="checkbox"></td>
<td>Enable</td>
<td>WAN</td>
<td>222.165.185.1-222.165.185.6</td>
<td>web,ping</td>
<td>80,--</td>
</tr>
</table>
</body>
</html>
"""

SAMPLE_TR069_HTML = """
<!DOCTYPE html>
<html>
<body>
<input type="text" name="url" value="http://acs.slt.lk">
<input type="text" name="username" value="acs@slt">
<input type="text" name="interval" value="10800">
<input type="text" name="conreqport" value="7547">
<input type="text" name="conreqpath" value="/tr069">
<input type="text" name="conreqname" value="502B73-MOCK000000">
</body>
</html>
"""


class TestSuperAdminMock(unittest.TestCase):
    def setUp(self):
        self.super_client = TendaClient(username="administrator", password="mock_super_admin_pass_xyz")
        self.super_client.role = "administrator"

        self.normal_client = TendaClient(username="admin", password="admin")
        self.normal_client.role = "admin"

    @patch.object(TendaClient, "_get_page")
    def test_get_wan_profiles(self, mock_get):
        mock_get.return_value = SAMPLE_STATUS_WAN_HTML
        profiles = self.super_client.get_wan_profiles()

        self.assertEqual(len(profiles), 3)

        p1 = profiles[0]
        self.assertEqual(p1.interface_name, "ppp0_nas0_0")
        self.assertEqual(p1.vlan_id, 20)
        self.assertEqual(p1.connection_type, "INTERNET_TR069")
        self.assertEqual(p1.protocol, "PPPoE")
        self.assertEqual(p1.ipv4_address, "100.64.0.1")
        self.assertEqual(p1.status, "up")

        p2 = profiles[1]
        self.assertEqual(p2.interface_name, "nas0_1")
        self.assertEqual(p2.vlan_id, 10)
        self.assertEqual(p2.connection_type, "VOICE")
        self.assertEqual(p2.protocol, "IPoE")

        p3 = profiles[2]
        self.assertEqual(p3.interface_name, "nas0_2")
        self.assertEqual(p3.vlan_id, 30)
        self.assertEqual(p3.protocol, "Bridged")
        self.assertIsNone(p3.ipv4_address)

    @patch.object(TendaClient, "_get_page")
    def test_get_voip_config(self, mock_get):
        mock_get.return_value = SAMPLE_VOIP_HTML
        voip = self.super_client.get_voip_config()

        self.assertEqual(voip.phone_number, "+94112345678")
        self.assertEqual(voip.display_name, "0112345678")
        self.assertEqual(voip.sip_account, "+94112345678F0@sltims.lk")
        self.assertEqual(voip.sip_proxy, "ftth.sltims.lk")
        self.assertEqual(voip.sip_port, 5060)
        self.assertEqual(voip.domain, "sltims.lk")
        self.assertEqual(voip.outbound_proxy, "ftth.sltims.lk")
        self.assertEqual(voip.rtp_port, 5000)

    @patch.object(TendaClient, "_get_page")
    def test_get_acl_rules(self, mock_get):
        mock_get.return_value = SAMPLE_ACL_HTML
        rules = self.super_client.get_acl_rules()

        self.assertEqual(len(rules), 2)
        lan_rule = rules[0]
        self.assertEqual(lan_rule.interface_type, "LAN")
        self.assertEqual(lan_rule.state, "Enable")
        self.assertIsNone(lan_rule.ip_range)
        self.assertIn("ftp", lan_rule.services)
        self.assertIn("web", lan_rule.services)

        wan_rule = rules[1]
        self.assertEqual(wan_rule.interface_type, "WAN")
        self.assertEqual(wan_rule.state, "Enable")
        self.assertEqual(wan_rule.ip_range, "222.165.185.1-222.165.185.6")
        self.assertEqual(wan_rule.services, ["web", "ping"])

    @patch.object(TendaClient, "_get_page")
    def test_get_tr069_config(self, mock_get):
        mock_get.return_value = SAMPLE_TR069_HTML
        tr069 = self.super_client.get_tr069_config()

        self.assertEqual(tr069.acs_url, "http://acs.slt.lk")
        self.assertEqual(tr069.acs_username, "acs@slt")
        self.assertEqual(tr069.inform_interval_sec, 10800)
        self.assertEqual(tr069.connection_request_port, 7547)
        self.assertEqual(tr069.connection_request_path, "/tr069")
        self.assertEqual(tr069.connection_request_username, "502B73-MOCK000000")

    def test_permission_denied_for_normal_admin(self):
        with self.assertRaises(TendaAuthError):
            self.normal_client.get_voip_config()

        with self.assertRaises(TendaAuthError):
            self.normal_client.get_acl_rules()

        with self.assertRaises(TendaAuthError):
            self.normal_client.get_tr069_config()

    def test_mcp_super_admin_unconfigured_password_error(self):
        with patch.dict("os.environ", {"TENDA_SUPER_PASSWORD": ""}):
            # Test that calling a super admin tool without a password returns error JSON
            with patch("tenda_controller.mcp_server.DEFAULT_SUPER_PASS", ""):
                res_str = tenda_get_wan_profiles(password="")
                res = json.loads(res_str)
                self.assertIn("error", res)
                self.assertIn("TENDA_SUPER_PASSWORD", res["error"])


if __name__ == "__main__":
    unittest.main()
