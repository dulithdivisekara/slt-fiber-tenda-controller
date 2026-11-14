"""
Unit tests for headless Chrome CDP browser fallback driver.
"""

import asyncio
import builtins
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tenda_controller.browser_fallback import _eval_js, apply_wifi_via_chrome
from tenda_controller.exceptions import TendaConnectionError


class TestBrowserFallback(unittest.TestCase):
    def test_missing_chrome_raises_connection_error(self):
        with patch("tenda_controller.browser_fallback.shutil.which", return_value=None):
            with self.assertRaises(TendaConnectionError) as ctx:
                apply_wifi_via_chrome(
                    host="192.168.1.1",
                    username="admin",
                    password="admin",
                    band_index=1,
                    ssid="TestNet-2.4G",
                )
        self.assertIn("No Chrome/Chromium binary found", str(ctx.exception))

    def test_missing_websockets_raises_connection_error(self):
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "websockets" or name.startswith("websockets."):
                raise ImportError("No module named 'websockets'")
            return real_import(name, globals, locals, fromlist, level)

        with patch("tenda_controller.browser_fallback.shutil.which", return_value="/usr/bin/google-chrome"), \
             patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(TendaConnectionError) as ctx:
                apply_wifi_via_chrome(
                    host="192.168.1.1",
                    username="admin",
                    password="admin",
                    band_index=1,
                    ssid="TestNet-2.4G",
                )
        self.assertIn("websockets", str(ctx.exception))

    def test_eval_js_raises_on_exception_details(self):
        async def run():
            import itertools

            fake_ws = MagicMock()
            sent = []

            async def fake_send(payload):
                sent.append(json.loads(payload))

            async def fake_recv():
                cmd_id = sent[-1]["id"]
                return json.dumps({
                    "id": cmd_id,
                    "result": {"exceptionDetails": {"text": "Uncaught TypeError"}},
                })

            fake_ws.send = fake_send
            fake_ws.recv = fake_recv

            with self.assertRaises(TendaConnectionError) as ctx:
                await _eval_js(fake_ws, itertools.count(1), "bad()")
            self.assertIn("Uncaught TypeError", str(ctx.exception))

        asyncio.run(run())

    def test_chrome_cdp_command_sequence(self):
        class FakeWebSocketException(Exception):
            pass

        sent_commands = []
        navigated_urls = []
        evaluated_exprs = []

        class FakeWS:
            def __init__(self):
                self._queue = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

            async def send(self, payload):
                msg = json.loads(payload)
                cmd_id = msg["id"]
                method = msg["method"]
                params = msg.get("params", {})
                sent_commands.append((method, params))

                if method == "Page.navigate":
                    url = params["url"]
                    navigated_urls.append(url)
                    self._current_url = url
                    self._queue.append(json.dumps({"id": cmd_id, "result": {}}))
                elif method == "Runtime.evaluate":
                    expr = params["expression"]
                    evaluated_exprs.append(expr)
                    if expr == "document.readyState":
                        val = "complete"
                    elif expr == "window.location.href":
                        if "login.asp" in self._current_url:
                            val = "http://192.168.1.1/admin/index.html"
                        else:
                            val = self._current_url
                    else:
                        val = True
                    self._queue.append(json.dumps({"id": cmd_id, "result": {"result": {"value": val}}}))
                else:
                    self._queue.append(json.dumps({"id": cmd_id, "result": {}}))

            async def recv(self):
                return self._queue.pop(0)

        fake_websockets = types.ModuleType("websockets")
        fake_websockets.connect = MagicMock(return_value=FakeWS())
        fake_ws_exc = types.ModuleType("websockets.exceptions")
        fake_ws_exc.WebSocketException = FakeWebSocketException
        fake_websockets.exceptions = fake_ws_exc

        fake_proc = MagicMock()
        fake_proc.terminate = MagicMock()
        fake_proc.wait = MagicMock(return_value=0)

        fake_resp = MagicMock()
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)
        fake_resp.read = MagicMock(
            return_value=json.dumps([
                {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}
            ]).encode("utf-8")
        )

        async def fast_sleep(_delay):
            return None

        with patch.dict(sys.modules, {"websockets": fake_websockets, "websockets.exceptions": fake_ws_exc}), \
             patch("tenda_controller.browser_fallback.shutil.which", return_value="/usr/bin/google-chrome"), \
             patch("tenda_controller.browser_fallback.subprocess.Popen", return_value=fake_proc), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="9222\n/devtools/browser/1"), \
             patch("tenda_controller.browser_fallback.urllib.request.urlopen", return_value=fake_resp), \
             patch("tenda_controller.browser_fallback.requests.post") as mock_post, \
             patch("tenda_controller.browser_fallback.asyncio.sleep", side_effect=fast_sleep):
            ok = apply_wifi_via_chrome(
                host="192.168.1.1",
                username="admin",
                password="admin",
                band_index=1,
                ssid="TestNet-2.4G",
                wifi_password="MockPass@2026",
                timeout=15.0,
            )

        self.assertTrue(ok)
        self.assertEqual(
            navigated_urls,
            [
                "http://192.168.1.1/admin/login.asp",
                "http://192.168.1.1/boaform/formWlanRedirect?redirect-url=/wlbasic.asp&wlan_idx=1",
                "http://192.168.1.1/boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx=1",
            ],
        )
        self.assertTrue(any("TestNet-2.4G" in expr for expr in evaluated_exprs))
        self.assertTrue(any("MockPass@2026" in expr for expr in evaluated_exprs))
        mock_post.assert_called_once()
        self.assertIn("/boaform/admin/formLogout", mock_post.call_args[0][0])
        fake_proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
