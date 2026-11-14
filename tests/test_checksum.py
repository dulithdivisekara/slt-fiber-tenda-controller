"""
Unit tests for Realtek / Boa postTableEncrypt checksum algorithm.
"""

import unittest
from tenda_controller.client import calculate_rtk_checksum, rtk_urlencode


class TestChecksum(unittest.TestCase):
    def test_backup_checksum(self):
        # Known test vector for saveCSConfig
        s = "save_cs=Backup...&"
        csum = calculate_rtk_checksum(s)
        self.assertEqual(csum, 52232, f"Expected 52232, got {csum}")

    def test_login_checksum(self):
        # Known test vector for admin login
        s = "username=admin&password=admin&timezone=17%3A30&dst_enabled=OFF&save=Login&submit-url=%2Fadmin%2Flogin.asp&"
        csum = calculate_rtk_checksum(s)
        self.assertEqual(csum, 63754, f"Expected 63754, got {csum}")

    def test_rtk_urlencode(self):
        self.assertEqual(rtk_urlencode("hello world"), "hello+world")
        self.assertEqual(rtk_urlencode("test!"), "test%21")
        self.assertEqual(rtk_urlencode("admin's"), "admin%27s")
        self.assertEqual(rtk_urlencode("(test)"), "%28test%29")
        self.assertEqual(rtk_urlencode("~test"), "%7Etest")


if __name__ == "__main__":
    unittest.main()
