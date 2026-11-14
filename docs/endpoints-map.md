# Tenda HG7 Complete Endpoint & Form Mapping

An exhaustive technical reference of all 44 web pages and backend CGI endpoints on the Tenda HG7 GPON ONT Router (Boa 0.95.15 web server).

## 1. Authentication & Session Endpoints

| URL Path | HTTP Method | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `/boaform/admin/formLogin` | `POST` | `username`, `password`, `timezone`, `dst_enabled`, `save=Login`, `submit-url`, `postSecurityFlag` | Authenticates web user against local MIB table. Returns 301/302 on success. |
| `/boaform/admin/formLogout` | `POST` | `save=Logout`, `submit-url=/login.asp`, `postSecurityFlag` | Destroys active session on router, releasing the 5-minute session lock. |
| `/boaform/admin/formAutoLogoutTime` | `POST` | `auto_logout_time`, `submit-url`, `postSecurityFlag` | Configures session inactivity timeout (default: 300 seconds). |

## 2. Wireless Local Area Network (WLAN) Endpoints

| URL Path | HTTP Method | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `/boaform/formWlanRedirect` | `GET` | `redirect-url`, `wlan_idx` | Switches the active radio context in Boa memory (`wlan_idx=0` for 5GHz, `wlan_idx=1` for 2.4GHz). |
| `/boaform/formWlanSetup` | `POST` | `wlan_idx`, `band`, `mode`, `ssid`, `chan`, `save=Apply+Changes`, `submit-url`, `postSecurityFlag` | Updates SSID broadcast name, RF channels, and channel width. |
| `/boaform/admin/formWlEncrypt` | `POST` | `wlan_idx`, `method`, `wpaAuth`, `pskFormat`, `pskValue`, `save=Apply+Changes`, `submit-url`, `postSecurityFlag` | Updates WPA2-PSK passphrase. `pskValue` MUST be base64-encoded. |
| `/boaform/admin/formAdvanceSetup` | `POST` | `wlan_idx`, `fragThreshold`, `rtsThreshold`, `beaconInterval`, `dtimPeriod`, `postSecurityFlag` | Configures beacon intervals and 802.11 aggregation. |
| `/boaform/admin/formWlAc` | `POST` | `wlan_idx`, `ac_action`, `mac`, `postSecurityFlag` | Configures MAC address access control lists. |
| `/boaform/formWsc` | `POST` | `wlan_idx`, `wsc_enable`, `postSecurityFlag` | Wi-Fi Protected Setup controls. |

## 3. Optical Network (GPON) & Telemetry

| URL Path | HTTP Method | Output Data | Description |
| :--- | :--- | :--- | :--- |
| `status_pon.asp` | `GET` | Rx dBm, Tx dBm, temp (°C), voltage (V), bias (mA), ONU State | Optical transceiver diagnostic sensors. |
| `admin/pon-stats.asp` | `GET` | BIP error counters, GEM frames, FEC corrected bits | Low-level GPON framer telemetry. |
| `omci_info.asp` | `GET` | Vendor ID (`TDTC`), Software version 1 & 2 | OMCI ME management information. |
| `stats.asp` | `GET` | Packets transmitted/received on LAN/WLAN/WAN interfaces | Linux kernel network interface statistics. |

## 4. System Administration & Diagnostics

| URL Path | HTTP Method | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `/boaform/formSaveConfig` | `POST` | `save_cs=Backup...`, `postSecurityFlag` | Downloads raw `config.xml`. Parameter `reset` must be omitted. |
| `/boaform/formPing` | `POST` | `pingAddr`, `ping_test=Start`, `submit-url`, `postSecurityFlag` | Synchronously executes 4-packet ICMP ping. |
| `/boaform/admin/formReboot` | `POST` | `reboot=Reboot`, `submit-url`, `postSecurityFlag` | Triggers a soft reboot of the ONT. |
| `/boaform/formNtp` | `POST` | `timeZone`, `ntpServerId`, `submit-url`, `postSecurityFlag` | Configures NTP time synchronization. |
