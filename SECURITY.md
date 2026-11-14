# Security Policy

## Supported Versions

| Version | Supported | Maintenance Status |
| :--- | :--- | :--- |
| 1.2.x | Yes | Active Development & Bug Fixes |
| 1.1.x | Yes | Security Updates Only |
| < 1.1.0 | No | Deprecated |

## Reporting a Vulnerability

If you discover a security vulnerability within the **SLT Fiber Tenda HG7 Controller** codebase or its interaction with embedded Boa web servers, please report it privately:

- **Email**: `security@divisekara.me`
- **GPG Key**: Available upon request or via keyserver.
- **Response Timeline**: Acknowledgement within 48 hours; assessment and patch proposal within 7 business days.

Please do not open public GitHub issues for undisclosed security vulnerabilities.

## Hardware & Firmware Security Advisories

The Tenda HG7 ONT operates on an embedded Realtek RTL960x SoC running the **Boa 0.95.15** web server at [http://192.168.1.1](http://192.168.1.1). The following domain-specific security considerations apply:

### 1. Embedded Checksum Authentication (`postSecurityFlag`)
All state-modifying requests require a calculated `postSecurityFlag` token. This token is derived using a 32-bit one's complement folding checksum over the serialized query string (`common.js`). While not a cryptographically secure HMAC, it acts as an anti-automation barrier. This library replicates the checksum calculation client-side for legitimate automation.

### 2. ISP Remote Management Exposure (ACL Table 5)
Audit of the router's Access Control Lists (`acl.asp`) reveals that SLT-MOBITEL provisions a default WAN management rule:
- **Interface**: WAN
- **Authorized IP Range**: `222.165.185.1 - 222.165.185.6`
- **Exposed Services**: `web` (HTTP port 80), `ping` (ICMP echo)
- **Implication**: Devices within this SLT technician subnet can query the web management portal from the upstream optical distribution network. It is strongly advised to maintain strong administrator credentials.

### 3. Session Lockout Mechanics
The router firmware enforces a hard concurrency limit:
- `AUTO_LOGOUT_TIME` is set to `300` seconds (5 minutes).
- If an automated script authenticates and fails to invoke `logout()`, the web UI and subsequent API calls remain locked for up to 5 minutes.
- The `TendaClient` class implements context managers (`__enter__` / `__exit__`) that guarantee immediate session destruction via `/boaform/admin/formLogout`.

### 4. Hardcoded Safety Protections on ISP Subsystems
To prevent accidental disconnection or loss of broadband Internet, landline VoIP telephony, or PeoTV multicast services:
- **WAN Interface Mutation Lock**: Automated write operations against `ATM_VC_TBL` (`multi_wan_generic.asp` / `waneth.asp`) are permanently blocked in client code.
- **Factory Reset Lock**: The `backup_config()` routine explicitly inspects the HTTP request payload and raises a `TendaDangerousOperationError` if the `reset` keyword is detected.
- **Passphrase Character Filtering**: Passphrases containing backslashes, single quotes, or double quotes (`/[\\'"]/`) are rejected client-side to prevent command injection into underlying shell scripts on the router.

### 5. Credential Isolation & Environment Protection
- Never commit exported `.xml` backups or `.env` files to source control.
- Ensure all `.xml`, `.bin`, and `.dat` files remain strictly excluded via `.gitignore`.
- Always store sensitive subscriber credentials in local `.env` files or export them as environment variables.

### 6. Ethical Boundaries & Abuse Prevention Policy
- This software is strictly intended for network subscribers and authorized engineers managing and automating their **own locally provisioned equipment**.
- This project will **never provide, develop, or accept pull requests for tools, scripts, or attack methodologies designed to discover, harvest, scan, or exploit credentials belonging to other subscribers or third-party networks**.
