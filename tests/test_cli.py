"""
Unit tests for CLI argument parsing and stderr error output.
"""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from rich.console import Console

from tenda_controller import cli
from tenda_controller.exceptions import TendaError


class TestCLI(unittest.TestCase):
    def test_wifi_set_parses_wifi_password_without_clobbering_router_password(self):
        parser = cli.create_parser()

        args1 = parser.parse_args(
            ["-p", "admin", "wifi", "set", "-b", "2.4g", "-s", "TestNet-2.4G", "-w", "MockPass@2026"]
        )
        self.assertEqual(args1.password, "admin")
        self.assertEqual(args1.wifi_password, "MockPass@2026")
        self.assertEqual(args1.band, "2.4g")
        self.assertEqual(args1.ssid, "TestNet-2.4G")
        self.assertFalse(args1.fallback_browser)

        args2 = parser.parse_args([
            "wifi",
            "set",
            "-b",
            "2.4g",
            "-s",
            "TestNet-2.4G",
            "--password",
            "MockPass@2026",
            "--host",
            "192.168.1.2",
            "--router-password",
            "secret",
            "--fallback-browser",
        ])
        self.assertEqual(args2.host, "192.168.1.2")
        self.assertEqual(args2.password, "secret")
        self.assertEqual(args2.wifi_password, "MockPass@2026")
        self.assertTrue(args2.fallback_browser)

    def test_wifi_show_preserves_password_and_host(self):
        parser = cli.create_parser()
        args = parser.parse_args(["wifi", "show", "--host", "192.168.1.1", "-u", "admin", "-p", "admin"])
        self.assertEqual(args.command, "wifi")
        self.assertEqual(args.wifi_action, "show")
        self.assertEqual(args.host, "192.168.1.1")
        self.assertEqual(args.username, "admin")
        self.assertEqual(args.password, "admin")

    def test_cli_error_writes_to_stderr(self):
        stderr_buf = io.StringIO()
        stdout_buf = io.StringIO()
        test_err_console = Console(file=stderr_buf, emoji=False, force_terminal=False)
        test_out_console = Console(file=stdout_buf, emoji=False, force_terminal=False)

        mock_client = MagicMock()
        mock_client.__enter__.side_effect = TendaError("boom router failure")

        with patch.object(cli, "err_console", test_err_console), \
             patch.object(cli, "console", test_out_console), \
             patch.object(cli, "TendaClient", return_value=mock_client), \
             patch.object(sys, "argv", ["tenda-ctl", "status"]):
            with self.assertRaises(SystemExit) as ctx:
                cli.main()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("boom router failure", stderr_buf.getvalue())
        self.assertEqual(stdout_buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
