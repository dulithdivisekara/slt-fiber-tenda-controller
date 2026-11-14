# Python SDK API Reference

Technical documentation for the `tenda_controller` package.

## `TendaClient`

The primary class for communicating with the router.

```python
from tenda_controller import TendaClient

with TendaClient(host="192.168.1.1", username="admin", password="admin") as client:
    status = client.get_status()
    print(status.lan_ip)
```

### Methods

#### `login() -> bool`
Authenticates against `/boaform/admin/formLogin` using Realtek checksum calculation.

#### `logout() -> bool`
Destroys the session via `/boaform/admin/formLogout`, freeing the router's session lock immediately.

#### `get_status() -> DeviceStatus`
Returns:
- `device_name`: str
- `software_version`: str
- `hardware_version`: str
- `uptime`: str
- `cpu_usage_pct`: float
- `memory_usage_pct`: float
- `dns_servers`: list[str]
- `lan_ip`: str
- `lan_mac`: str

#### `get_pon_status() -> PonStatus`
Returns:
- `temperature_c`: float
- `voltage_v`: float
- `tx_power_dbm`: float
- `rx_power_dbm`: float
- `bias_current_ma`: float
- `onu_state`: str ("O5" = Operational)

#### `get_connected_devices() -> List[ConnectedDevice]`
Returns active devices with:
- `interface_type`: "WLAN" | "LAN"
- `hostname`: str
- `mac_address`: str
- `ipv4_address`: Optional[str]
- `ipv6_address`: Optional[str]

#### `get_wifi_config(band: str) -> WifiConfig`
Accepts `"2.4g"` or `"5g"`. Returns `WifiConfig`.

#### `set_wifi_config(band: str, ssid: Optional[str] = None, password: Optional[str] = None, use_browser_fallback: bool = True, force_browser_fallback: bool = False) -> bool`
Safely updates SSID and/or password with read-back verification (`wlbasic.asp` / `wlwpa.asp`) and optional headless Chrome CDP fallback. Base64 encodes passwords automatically. Rejects quotes, backslashes, and spaces.

#### `backup_config(destination_path: Union[str, Path]) -> Path`
Exports the complete pristine XML configuration backup. Enforces safety checks to block factory reset.

#### `ping(target: str, timeout: float = 15.0) -> PingResult`
Executes ICMP ping diagnostic.

#### `reboot() -> bool`
Triggers router reboot.
