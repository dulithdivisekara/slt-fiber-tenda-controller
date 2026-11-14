<p align="center">
  <img src="assets/tenda-logo.png" width="200" alt="Tenda Logo" />
</p>

<h1 align="center">SLT Fiber Tenda HG7 Router Controller</h1>

<p align="center">
  Autonomous AI agent control ecosystem, FastMCP server, and CLI management utility for Tenda HG7 GPON ONT routers deployed on Sri Lanka Telecom (SLT-MOBITEL) fiber optic broadband.
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python Version"></a>
  <a href="#"><img src="https://img.shields.io/badge/Protocol-Model%20Context%20Protocol-orange?style=flat-square" alt="Protocol"></a>
  <a href="#"><img src="https://img.shields.io/badge/Hardware-Tenda%20HG7%20AC1200-green?style=flat-square" alt="Hardware"></a>
  <a href="#"><img src="https://img.shields.io/badge/ISP-SLT--MOBITEL%20Fiber-purple?style=flat-square" alt="ISP"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <a href="#overview">Overview</a> &bull;
  <a href="#architecture--role-privileges">Architecture</a> &bull;
  <a href="#project-structure">Structure</a> &bull;
  <a href="#installation">Installation</a> &bull;
  <a href="#tool-catalog--usage">Tools & Usage</a> &bull;
  <a href="#super-admin-inspection">Super Admin</a> &bull;
  <a href="#model-context-protocol-server">MCP Server</a> &bull;
  <a href="#verification-tests">Testing</a> &bull;
  <a href="#security--isp-safety-boundaries">Security</a> &bull;
  <a href="#license">License</a>
</p>

## Overview

The **SLT Fiber Tenda HG7 Controller** provides programmatic automation and autonomous agent integration for the Tenda HG7 Dual-Band AC1200 GPON ONT router deployed across Sri Lanka Telecom (SLT-MOBITEL) fiber optic broadband lines. Built on a Realtek RTL960x SoC running the embedded Boa 0.95.15 web server accessible at [http://192.168.1.1](http://192.168.1.1), the router normally requires manual web dashboard interactions, lacks an official REST API, and locks out concurrent administrator sessions.

This project delivers:
- **Autonomous Agent Control via MCP**: A standards-compliant Model Context Protocol server exposing 12 structured tools for optical telemetry, device inventories, diagnostic ping, Wi-Fi mutations, WAN profiles, VoIP SIP status, and TR-069 configuration to AI assistants (Google Antigravity, Claude, Cursor).
- **Engineering CLI (`tenda-ctl`)**: Global command-line interface with formatted terminal tables for network administrators and engineers.
- **Dual-Role Architecture**: Transparent support for both standard end-user (`admin`) and ISP Super Administrator (`administrator`) privilege levels with dynamic role detection.
- **Protocol Emulation Engine**: Reverse-engineered implementation of Realtek's 32-bit checksum algorithm (`postTableEncrypt`), automatic session lifecycle teardown, and base64 passphrase encryption.
- **Strict ISP Safety Protections**: Hardcoded write-protection guardrails that prevent accidental modification of SLT WAN VLANs (VLAN 20 Internet PPPoE, VLAN 10 Voice IPoE, VLAN 30 PeoTV) or optical registration states.

## Architecture & Role Privileges

The embedded web server dynamically binds client sessions to distinct JavaScript menus based on the authenticated credentials.

| Feature / Subsystem | Standard Admin (`admin`) | Super Admin (`administrator`) | Technical Details |
| :---: | :---: | :---: | :---: |
| **Active Interface Script** | `admin/userMenu.js` | `adminMenu.js` | Embedded Boa server binds menu script per IP session. |
| **Top-Level Navigation** | 8 Modules | 10 Modules | Unlocks **WAN** (Sub 4) and **VoIP** (Sub 6). |
| **Broadband WAN Profiles** | Hidden | Full Inspection | VLAN 20 Internet PPPoE, VLAN 10 Voice IPoE, VLAN 30 PeoTV. |
| **Landline VoIP Telephony** | Hidden | Full Inspection | SIP Proxy (`ftth.sltims.lk:5060`), Domain, RTP port 5000. |
| **Access Control Lists (ACL)** | Hidden | Full Inspection | Management access rules for Telnet, SSH, HTTP, HTTPS, ICMP. |
| **TR-069 CWMP Management** | Hidden | Full Inspection | SLT ACS URL (`http://acs.slt.lk`), inform interval, credentials. |
| **Port Mirroring** | Hidden | Full Inspection | Frame mirroring to monitor port for packet analysis. |
| **WLAN, DHCP, Firewall** | Accessible | Accessible | Wi-Fi SSIDs, passphrases, MAC filtering, port forwarding. |

```mermaid
sequenceDiagram
    autonumber
    actor User as Engineer / AI Agent
    participant CLI as tenda-ctl / MCP Server
    participant Core as TendaClient Engine
    participant Router as Tenda HG7 (192.168.1.1)

    User->>CLI: Execute Command / Tool Call
    CLI->>Core: Authenticate (admin / administrator)
    Core->>Router: POST /boaform/admin/formLogin (Checksum + Referer)
    Router-->>Core: HTTP 301/302 Redirect (Session Active)
    Core->>Router: GET/POST Target Endpoint (e.g. status_pon.asp)
    Router-->>Core: Raw HTML / XML Response
    Core->>Router: POST /boaform/admin/formLogout (Release 5-min Lock)
    Core->>CLI: Parsed Pydantic Model
    CLI->>User: Formatted Rich Table / JSON-RPC Response
```

## Project Structure

```
.
├── assets/
│   ├── screenshots/               # Sanitized terminal outputs (help, status, pon)
│   └── tenda-logo.png             # Optimized official transparent logo
├── docs/
│   ├── api-reference.md           # Python client methods and schemas
│   ├── endpoints-map.md           # Complete 44-page router endpoint mapping
│   └── super-admin-guide.md       # Technical guide to Super Admin subsystems
├── tenda_controller/
│   ├── __init__.py                # Package exports and version metadata
│   ├── browser_fallback.py        # Headless Chrome CDP fallback for Wi-Fi mutations
│   ├── client.py                  # HTTP client, checksum, and session engine
│   ├── cli.py                     # Rich command-line interface (tenda-ctl)
│   ├── exceptions.py              # Domain error types and safety guardrails
│   ├── mcp_server.py              # FastMCP server for AI agent tool calling
│   └── models.py                  # Pydantic schemas for router telemetry
├── tests/
│   ├── __init__.py
│   ├── test_browser_fallback.py   # Mock unit tests for Chrome CDP fallback
│   ├── test_checksum.py           # Verification of Realtek checksum vectors
│   ├── test_cli.py                # Unit tests for CLI subparser & error routing
│   ├── test_client_mock.py        # Mock unit tests for basic client parsers
│   └── test_super_admin_mock.py   # Mock unit tests for Super Admin parsers
├── .env.example                   # Environment configuration template
├── CODE_OF_CONDUCT.md             # Contributor Covenant Code of Conduct v2.1
├── CONTRIBUTING.md                # Development, testing, and PR guidelines
├── install.sh                     # Turnkey system installer script
├── LICENSE                        # MIT License
├── pyproject.toml                 # Build configuration (setuptools)
├── README.md                      # Project documentation
├── requirements.txt               # Pinned runtime dependencies
└── SECURITY.md                    # Security advisories and disclosure policy
```

## Installation

### Method 1: Turnkey One-Line Installer (Recommended)
Clone the repository and run the automated installer script:
```bash
git clone https://github.com/dulithdivisekara/slt-fiber-tenda-controller.git
cd slt-fiber-tenda-controller
chmod +x install.sh
./install.sh
```

The installer automatically:
- Checks Python 3.10+ and pip availability.
- Handles PEP 668 environments (`--break-system-packages`).
- Deploys `tenda-ctl` into `~/.local/bin`.
- Cleans up legacy binary artifacts.
- Ensures `~/.local/bin` is exported in your shell profile (`~/.bashrc`, `~/.zshrc`, `~/.profile`).

### Method 2: Standard Pip Install
```bash
# Inside a virtual environment:
pip install -e .

# Or user-mode install on modern Linux:
pip install --break-system-packages --user -e .

# Optional: include headless Chrome CDP fallback support for Wi-Fi mutations:
pip install -e ".[browser]"
```

### Method 3: Environment Configuration
Copy the sample environment template and set credentials for automated tools:
```bash
cp .env.example .env
```

```bash
TENDA_HOST=192.168.1.1
TENDA_USERNAME=admin
TENDA_PASSWORD=admin
TENDA_SUPER_USERNAME=administrator
TENDA_SUPER_PASSWORD=your_super_admin_password_here
```

## Tool Catalog & Usage

The `tenda-ctl` utility provides 7 core subscriber commands and 4 ISP Super Admin inspection commands:

<p align="center">
  <img src="assets/screenshots/tenda-ctl-help.png" width="700" alt="tenda-ctl CLI Help Overview" />
</p>

| Command | Purpose | Access Tier | Practical Value for SLT Subscribers |
| :---: | :---: | :---: | :---: |
| `status` | System Telemetry | Normal (`admin`) | Check CPU/RAM load, firmware version, and uptime. |
| `pon` | Optical Power Levels | Normal (`admin`) | Verify fiber Rx/Tx optical power (dBm) and ONU registration (`O5`). |
| `devices` | Connected Device Inventory | Normal (`admin`) | Monitor active LAN Ethernet and Wi-Fi DHCP clients. |
| `wifi` | Wireless Configuration | Normal (`admin`) | Safely update 2.4 GHz and 5 GHz SSIDs/passwords without touching WAN. |
| `backup` | Disaster Recovery Backup | Normal (`admin`) | Export full router XML configuration before making any modifications. |
| `ping` | Diagnostic Connectivity | Normal (`admin`) | Send ICMP ping upstream to test internet routing. |
| `reboot` | Graceful Restart | Normal (`admin`) | Soft reboot router remotely without power cycling. |

> [!NOTE]
> The 4 advanced ISP commands (`wan`, `voip`, `acl`, `tr069`) require Super Admin credentials (`--super`) and are documented in the [Super Admin Guide](docs/super-admin-guide.md).

### System Telemetry & Hardware Status
```bash
tenda-ctl status
```

<p align="center">
  <img src="assets/screenshots/tenda-ctl-status.png" width="450" alt="tenda-ctl status terminal output displaying HG7 v2.0 hardware, v1.0.17 firmware, CPU, RAM, and uptime" />
</p>

### Optical Fiber Power (PON) Diagnostics
Check your fiber link health directly from your terminal:
```bash
tenda-ctl pon
```

<p align="center">
  <img src="assets/screenshots/tenda-ctl-pon.png" width="550" alt="tenda-ctl pon optical power telemetry output displaying ONU state O5, Rx power -26.20 dBm, and Tx power 1.69 dBm" />
</p>

*Optical Compliance Standards: SLT Class B+ GPON requires Rx optical power between `-8.0 dBm` and `-28.0 dBm` with ONU State `O5` (Operational / Synchronized).*

### Connected Client Inventory
```bash
tenda-ctl devices
```

### Wireless Network Inspection & Mutation
Inspect current wireless configurations:
```bash
tenda-ctl wifi show
```

Safely update wireless network credentials without risking internet disconnects:
```bash
# Update 5GHz SSID and Passphrase
tenda-ctl wifi set --band 5g --ssid "SLT-Fiber-5G" --password "YourStrongPassword123"

# Update 2.4GHz SSID
tenda-ctl wifi set --band 2.4g --ssid "SLT-Fiber-2.4G"

# Force headless Chrome CDP fallback if firmware rejects direct HTTP forms
tenda-ctl wifi set --band 5g --ssid "SLT-Fiber-5G" --fallback-browser
```

### Configuration Backup & Export
```bash
tenda-ctl backup backup_config.xml
```

### Upstream Network Ping
```bash
tenda-ctl ping 1.1.1.1
```

## Super Admin Inspection

Authenticate with ISP Super Administrator credentials via `--super` or the `TENDA_SUPER_PASSWORD` environment variable to inspect low-level fiber infrastructure subsystems:

```bash
# Broadband multi-WAN interface profiles (VLAN 20 Internet, VLAN 10 Voice, VLAN 30 PeoTV)
tenda-ctl wan --super

# Landline VoIP SIP telephony registrar and media configuration
tenda-ctl voip --super

# Remote management Access Control Lists (ACL rules on LAN and WAN)
tenda-ctl acl --super

# TR-069 Auto-Configuration Server (ACS) CWMP telemetry
tenda-ctl tr069 --super
```

> [!TIP]
> For complete technical breakdowns of WAN VLAN bindings, SIP domain configurations, ACL port maps, and TR-069 parameters, refer to the dedicated [Super Admin Technical Guide](docs/super-admin-guide.md).

## Model Context Protocol Server

The controller exposes 12 structured tools for autonomous AI agents via FastMCP.

### Quick Setup for AI Agents (One-Shot Prompt)

If you use an AI coding assistant (such as Google Antigravity, Claude Code, Cursor, Windsurf, or Cline), paste the following prompt directly into your AI chat to install and configure this MCP server automatically on your machine:

> **Agent Installation Prompt**:
> ```text
> Please install and configure the Tenda HG7 Router Controller MCP server on this machine:
> 
> 1. Check if https://github.com/dulithdivisekara/slt-fiber-tenda-controller.git is already cloned; if not, clone it and enter the directory:
>    git clone https://github.com/dulithdivisekara/slt-fiber-tenda-controller.git
>    cd slt-fiber-tenda-controller
> 
> 2. Install the package in editable mode with dependencies:
>    pip install -e .
> 
> 3. Register the MCP server named "tenda-hg7" in my agent/environment MCP configuration file (e.g., mcp.json, claude_desktop_config.json, or agent-specific MCP settings):
>    - Command: python3 (or absolute path to current python virtual environment)
>    - Args: ["-m", "tenda_controller.mcp_server"]
>    - Environment variables:
>      - TENDA_HOST: "192.168.1.1" (or router gateway IP)
>      - TENDA_USERNAME: "admin"
>      - TENDA_PASSWORD: "admin"
>      - (Optional for advanced ISP diagnostics) TENDA_SUPER_USERNAME: "administrator", TENDA_SUPER_PASSWORD: "<your-super-admin-password>"
> 
> 4. Verify connectivity by invoking the tool `tenda_get_status` or running `tenda-ctl status`.
> 5. Confirm when the MCP server is registered and print the router status, optical Rx power, and firmware version.
> ```

### Manual Configuration (Claude Desktop / Antigravity / Cursor)
Add the server entry to your MCP configuration file (`mcp.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tenda-hg7": {
      "command": "python3",
      "args": ["-m", "tenda_controller.mcp_server"],
      "env": {
        "TENDA_HOST": "192.168.1.1",
        "TENDA_USERNAME": "admin",
        "TENDA_PASSWORD": "admin",
        "TENDA_SUPER_USERNAME": "administrator",
        "TENDA_SUPER_PASSWORD": "<SUPER_ADMIN_PASSWORD>"
      }
    }
  }
}
```

### Complete Tool Inventory
- `tenda_get_status()`: Hardware status, software version, CPU, memory, and uptime.
- `tenda_get_optical_power()`: Rx/Tx optical power (dBm), laser temperature, voltage, and ONU state.
- `tenda_get_connected_devices()`: Real-time list of all LAN and WLAN connected client devices.
- `tenda_get_wifi_config(band)`: Inspect active SSID, channel, and encryption for `"2.4g"` or `"5g"`.
- `tenda_set_wifi_config(band, ssid, password)`: Safely update Wi-Fi credentials with base64 encryption.
- `tenda_backup_config(destination_path)`: Export clean XML configuration file.
- `tenda_ping(target)`: Perform diagnostic ICMP ping from router to upstream host.
- `tenda_reboot()`: Dispatch a graceful soft restart to the router.
- `tenda_get_wan_profiles()`: Inspect SLT multi-WAN interfaces (VLAN 20, 10, 30).
- `tenda_get_voip_config()`: Inspect SLT landline SIP proxy, domain, and media ports.
- `tenda_get_acl_rules()`: Inspect management service Access Control List exposure.
- `tenda_get_tr069_config()`: Inspect TR-069 Auto-Configuration Server parameters.

### Controlling the Router via AI Agents (Antigravity & Claude)

FastMCP exposes the router controller over standard I/O (stdin/stdout) via JSON-RPC. Once registered, AI agents automatically discover the 12 tools and their parameter schemas.

#### Sample Agent Prompts
You can issue natural language commands directly to your AI assistant:
- **Optical Laser Diagnostics**:
  > *"Check my fiber optical power levels and confirm if the Rx dBm is within SLT's compliant range."*
  > &rarr; Dispatches `tenda_get_optical_power()`
- **Wi-Fi SSID & Password Management**:
  > *"Update my 5GHz Wi-Fi SSID to 'Example-Fiber-5G' and set the password to 'SecurePass2026'."*
  > &rarr; Dispatches `tenda_set_wifi_config(band="5g", ssid="Example-Fiber-5G", password="SecurePass2026")`
- **Connected Device Inventory**:
  > *"List all devices currently connected to my Wi-Fi and Ethernet ports."*
  > &rarr; Dispatches `tenda_get_connected_devices()`
- **Configuration Disaster Recovery**:
  > *"Export a full router configuration backup to local storage."*
  > &rarr; Dispatches `tenda_backup_config(destination_path="backup_config.xml")`
- **Upstream Latency Test**:
  > *"Ping 1.1.1.1 from the router to verify upstream connectivity."*
  > &rarr; Dispatches `tenda_ping(target="1.1.1.1")`

## Session Logging & Inspection

The client automatically manages session creation and teardown to prevent the router's 5-minute admin session lockout (`AUTO_LOGOUT_TIME=300`). 
- Sessions authenticate with custom Realtek checksum headers.
- Each context-managed command immediately logs out upon exit via `/boaform/admin/formLogout`.
- To inspect raw HTTP debug logs:
  ```bash
  python3 -c "import logging; logging.basicConfig(level=logging.DEBUG); from tenda_controller import TendaClient; c = TendaClient(); c.login(); print(c.get_status()); c.logout()"
  ```

## Verification Tests

Run the automated test suite verifying checksum calculation, parser robustness, CLI subparsers, browser fallback, and Super Admin mock fixtures:
```bash
python3 -m unittest discover -s tests -v
```

Expected summary: `Ran 28 tests ... OK` (covers `test_browser_fallback`, `test_checksum`, `test_cli`, `test_client_mock`, and `test_super_admin_mock`).

## Security & ISP Safety Boundaries

### Protection of Critical ISP Subsystems
The router is deployed on an active SLT Fiber connection carrying multi-VLAN traffic:
- **VLAN 20 (`ppp0_nas0_0`)**: Broadband Internet and TR-069 remote telemetry.
- **VLAN 10 (`nas0_1`)**: SLT Voice / VoIP IPoE interface.
- **VLAN 30 (`nas0_2`)**: PeoTV IPTV multicast bridged interface.

The `tenda-controller` engine hardcodes strict write protections:
- Under no circumstances will the tool submit requests targeting `ATM_VC_TBL` (WAN profiles) or `GPON_PLOAM`.
- The configuration backup routine specifically validates that the `reset` action keyword is absent, eliminating accidental factory reset risks.
- For complete security details, see [SECURITY.md](SECURITY.md).

### Ethical Boundaries & Credential Protection Policy
- This project is strictly designed for subscribers managing and automating their **own locally owned/rented CPE devices**.
- In adherence with responsible security practices, this project **will never provide, support, or integrate tools or scripts designed to harvest, scan, or discover credentials belonging to other subscribers or third-party networks**.

## Contributing & Governance

- See [CONTRIBUTING.md](CONTRIBUTING.md) for local development, testing, and PR submission guidelines.
- All contributors are expected to uphold the standards outlined in our [Code of Conduct](CODE_OF_CONDUCT.md).
- Detailed technical breakdowns of Super Admin subsystems can be found in the [Super Admin Guide](docs/super-admin-guide.md).

## License

This project is licensed under the [MIT License](LICENSE).

## Search Indexing & SLT Fiber Keywords

This repository is optimized for Sri Lankan fiber broadband subscribers, network administrators, and home automation developers:
- **Hardware & Firmware**: Tenda HG7 Dual-Band AC1200 GPON ONT, Realtek RTL960x SoC, Boa Web Server 0.95.15, firmware `v1.0.17`.
- **ISP Network Profiles**: SLT-MOBITEL Fiber (Sri Lanka Telecom FTTH), VLAN 20 Internet PPPoE, VLAN 10 Voice SIP VoIP (`ftth.sltims.lk`), VLAN 30 PeoTV IPTV multicast.
- **Diagnostics & Telemetry**: SLT optical power check (`tenda-ctl pon`), Class B+ laser attenuation limits (-8 dBm to -28 dBm), GPON ONU state `O5`.
- **AI Automation**: Model Context Protocol (MCP), FastMCP server, Google Antigravity router control, Claude Desktop networking tools.
