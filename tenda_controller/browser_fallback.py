"""
Headless Chrome DevTools Protocol (CDP) fallback driver for Tenda HG7 Wi-Fi settings.

Used when direct Boa HTTP form submission fails verification or is bypassed via
the browser fallback option.
"""

import asyncio
import itertools
import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator, Optional

import requests

from .exceptions import TendaAuthError, TendaConnectionError


async def _cdp_send(
    ws: Any,
    msg_id_counter: Iterator[int],
    method: str,
    params: Optional[dict] = None,
    timeout: float = 10.0,
) -> dict:
    """Sends a single CDP JSON-RPC command and waits for its matching response frame."""
    cmd_id = next(msg_id_counter)
    payload = json.dumps({"id": cmd_id, "method": method, "params": params or {}})
    await asyncio.wait_for(ws.send(payload), timeout=timeout)

    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TendaConnectionError(f"Timed out waiting for CDP response to {method}.")
        raw_msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw_msg)
        if msg.get("id") != cmd_id:
            continue
        if "error" in msg:
            err = msg["error"]
            err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise TendaConnectionError(f"CDP error in {method}: {err_msg}")
        return msg.get("result", {})


async def _eval_js(
    ws: Any,
    msg_id_counter: Iterator[int],
    expr: str,
    timeout: float = 10.0,
) -> Any:
    """Evaluates a JavaScript expression in the active page and returns its value."""
    result = await _cdp_send(
        ws,
        msg_id_counter,
        "Runtime.evaluate",
        {"expression": expr, "returnByValue": True},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        details = result["exceptionDetails"]
        desc = (
            details.get("exception", {}).get("description")
            or details.get("text")
            or "JS evaluation error"
        )
        raise TendaConnectionError(f"Browser JS error: {desc}")
    return result.get("result", {}).get("value")


async def _wait_for_ready_state(
    ws: Any,
    msg_id_counter: Iterator[int],
    timeout: float,
) -> None:
    """Polls document.readyState until 'complete' or timeout."""
    deadline = time.monotonic() + timeout
    while True:
        state = await _eval_js(ws, msg_id_counter, "document.readyState", timeout=5.0)
        if state == "complete":
            return
        if time.monotonic() >= deadline:
            raise TendaConnectionError("Timed out waiting for router page load.")
        await asyncio.sleep(0.15)


async def _navigate_and_wait(
    ws: Any,
    msg_id_counter: Iterator[int],
    url: str,
    timeout: float,
) -> None:
    """Navigates the browser page to url and waits for document completion."""
    await _cdp_send(ws, msg_id_counter, "Page.navigate", {"url": url}, timeout=timeout)
    await asyncio.sleep(0.3)
    await _wait_for_ready_state(ws, msg_id_counter, timeout)


def _discover_ws_debugger_url(port: int) -> str:
    """Queries Chrome's local /json/list endpoint for the first page WebSocket URL."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/list", timeout=3.0
        ) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        raise TendaConnectionError(
            f"Failed to query headless Chrome DevTools targets on port {port}: {exc}"
        ) from exc

    for item in targets:
        if isinstance(item, dict) and item.get("type") == "page" and "webSocketDebuggerUrl" in item:
            return item["webSocketDebuggerUrl"]

    raise TendaConnectionError("No page target found in headless Chrome DevTools /json/list.")


def _logout_boa_session(host: str) -> None:
    """Best-effort checksummed Boa logout so the IP-based session lock is released."""
    from .client import calculate_rtk_checksum, rtk_urlencode

    params = [("save", "Logout"), ("submit-url", "/login.asp")]
    query_str = "".join(f"{rtk_urlencode(k)}={rtk_urlencode(v)}&" for k, v in params)
    csum = calculate_rtk_checksum(query_str)
    post_body = f"{query_str}postSecurityFlag={csum}"
    try:
        requests.post(
            f"http://{host}/boaform/admin/formLogout",
            data=post_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"http://{host}/",
            },
            timeout=5.0,
        )
    except requests.RequestException:
        pass


async def _apply_wifi_via_chrome_async(
    chrome_bin: str,
    host: str,
    username: str,
    password: str,
    band_index: int,
    ssid: Optional[str],
    wifi_password: Optional[str],
    timeout: float,
) -> bool:
    """Launches headless Chrome via CDP and applies Wi-Fi changes through router UI forms."""
    try:
        import websockets
        from websockets.exceptions import WebSocketException
    except ImportError as exc:
        raise TendaConnectionError(
            "Browser fallback requires the 'websockets' package (pip install websockets)."
        ) from exc

    proc = None
    tmpdir = None
    login_attempted = False

    try:
        tmpdir = tempfile.TemporaryDirectory(prefix="tenda_cdp_")
        proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                "--remote-debugging-port=0",
                f"--user-data-dir={tmpdir.name}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-gpu",
                "--no-sandbox",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        port_file = Path(tmpdir.name) / "DevToolsActivePort"
        port: Optional[int] = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if port_file.exists():
                lines = port_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                if lines and lines[0].strip().isdigit():
                    port = int(lines[0].strip())
                    break
            await asyncio.sleep(0.05)

        if port is None:
            raise TendaConnectionError("Timed out waiting for headless Chrome DevToolsActivePort.")

        ws_url = _discover_ws_debugger_url(port)
        msg_id_counter = itertools.count(1)

        try:
            async with websockets.connect(ws_url, open_timeout=timeout) as ws:
                await _cdp_send(ws, msg_id_counter, "Page.enable", timeout=timeout)
                await _cdp_send(ws, msg_id_counter, "Runtime.enable", timeout=timeout)

                await _navigate_and_wait(
                    ws, msg_id_counter, f"http://{host}/admin/login.asp", timeout
                )
                login_attempted = True
                login_js = f"""
                (() => {{
                  document.getElementById('username').value = {json.dumps(username)};
                  document.getElementById('password').value = {json.dumps(password)};
                  document.getElementById('loginBtn').click();
                  return true;
                }})()
                """
                await _eval_js(ws, msg_id_counter, login_js, timeout=timeout)
                await asyncio.sleep(1.0)
                await _wait_for_ready_state(ws, msg_id_counter, timeout)

                current_url = await _eval_js(ws, msg_id_counter, "window.location.href", timeout=timeout)
                if "login.asp" in str(current_url or ""):
                    raise TendaAuthError(
                        "Browser fallback login failed: router returned login.asp."
                    )

                if ssid is not None or band_index == 1:
                    await _navigate_and_wait(
                        ws,
                        msg_id_counter,
                        f"http://{host}/boaform/formWlanRedirect?redirect-url=/wlbasic.asp&wlan_idx={band_index}",
                        timeout,
                    )
                    basic_url = await _eval_js(
                        ws, msg_id_counter, "window.location.href", timeout=timeout
                    )
                    if "login.asp" in str(basic_url or ""):
                        raise TendaAuthError(
                            "Browser fallback lost session before wlbasic.asp."
                        )

                    valid_bands = (
                        "['0','1','2','7','9','10']"
                        if band_index == 1
                        else "['3','7','11','63','71','75']"
                    )
                    fallback_band = "'10'" if band_index == 1 else "'75'"
                    wlbasic_submit_js = f"""
                    (() => {{
                      const f = document.wlanSetup;
                      if (f.wlanDisabled && f.wlanDisabled.checked) {{
                        f.wlanDisabled.checked = false;
                        updateState(f);
                      }}
                      const validBands = {valid_bands};
                      const fallbackBand = {fallback_band};
                      if (!validBands.includes(String(f.band.value))) {{
                        f.band.value = fallbackBand;
                        updateChan();
                      }}
                      if ({json.dumps(ssid)} !== null) {{
                        f.ssid.value = {json.dumps(ssid)};
                      }}
                      document.querySelector('form[name="wlanSetup"] input[name="save"]').click();
                      return true;
                    }})()
                    """
                    try:
                        await _eval_js(ws, msg_id_counter, wlbasic_submit_js, timeout=timeout)
                        await asyncio.sleep(4.0)
                    except (WebSocketException, TimeoutError, asyncio.TimeoutError, TendaConnectionError):
                        await asyncio.sleep(3.0)

                if wifi_password is not None:
                    await _navigate_and_wait(
                        ws,
                        msg_id_counter,
                        f"http://{host}/boaform/formWlanRedirect?redirect-url=/wlwpa.asp&wlan_idx={band_index}",
                        timeout,
                    )
                    wpa_url = await _eval_js(
                        ws, msg_id_counter, "window.location.href", timeout=timeout
                    )
                    if "login.asp" in str(wpa_url or ""):
                        raise TendaAuthError(
                            "Browser fallback lost session before wlwpa.asp."
                        )

                    wlwpa_submit_js = f"""
                    (() => {{
                      const f = document.formEncrypt;
                      f.wpaSSID.value = "0";
                      SSIDSelected(0);
                      f.security_method.value = "6";
                      show_authentication();
                      f.wpaAuth[1].checked = true;
                      show_wpa_settings();
                      if (!f.ciphersuite_a.disabled) f.ciphersuite_a.checked = true;
                      if (!f.wpa2ciphersuite_a.disabled) f.wpa2ciphersuite_a.checked = true;
                      f.pskFormat.value = "0";
                      f.pskValue.value = {json.dumps(wifi_password)};
                      document.querySelector('form[name="formEncrypt"] input[name="save"]').click();
                      return true;
                    }})()
                    """
                    try:
                        await _eval_js(ws, msg_id_counter, wlwpa_submit_js, timeout=timeout)
                        await asyncio.sleep(4.0)
                    except (WebSocketException, TimeoutError, asyncio.TimeoutError, TendaConnectionError):
                        await asyncio.sleep(3.0)
        except TendaAuthError:
            raise
        except (WebSocketException, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            raise TendaConnectionError(f"Browser CDP error: {exc}") from exc

        return True
    finally:
        if login_attempted:
            _logout_boa_session(host)
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except OSError:
                    pass
        if tmpdir is not None:
            try:
                tmpdir.cleanup()
            except OSError:
                pass


def apply_wifi_via_chrome(
    host: str,
    username: str,
    password: str,
    band_index: int,
    ssid: Optional[str] = None,
    wifi_password: Optional[str] = None,
    timeout: float = 25.0,
) -> bool:
    """
    Applies Wi-Fi SSID and/or WPA2-PSK password using a headless Chrome browser via CDP.
    """
    chrome_bin = next(
        (shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser") if shutil.which(b)),
        None,
    )
    if chrome_bin is None:
        raise TendaConnectionError("No Chrome/Chromium binary found for browser fallback.")

    return asyncio.run(
        _apply_wifi_via_chrome_async(
            chrome_bin=chrome_bin,
            host=host,
            username=username,
            password=password,
            band_index=band_index,
            ssid=ssid,
            wifi_password=wifi_password,
            timeout=timeout,
        )
    )
