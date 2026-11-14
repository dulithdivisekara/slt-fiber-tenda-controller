"""
CLI runner (tenda-ctl) for Tenda HG7 router.

Author: Dulith Divisekara
"""

import os
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .client import TendaClient
from .exceptions import TendaError

console = Console(emoji=False)


def create_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", default=None, help="Router IP address (default: 192.168.1.1)")
    common.add_argument("--username", "-u", default=None, help="Username (default: admin)")
    common.add_argument("--password", "-p", default=None, help="Password (default: admin)")
    common.add_argument("--timeout", "-t", type=float, default=10.0, help="HTTP timeout in seconds")
    common.add_argument(
        "--super",
        action="store_true",
        help="Authenticate using ISP Super Admin credentials (administrator)",
    )

    parser = argparse.ArgumentParser(
        prog="tenda-ctl",
        usage="%(prog)s [OPTIONS] COMMAND [ARGS]...",
        description="Autonomous CLI & Management Tool for Tenda HG7 GPON ONT Router (SLT Fiber)",
        parents=[common],
    )
    parser.add_argument("--version", "-v", action="version", version="slt-fiber-tenda-controller 1.2.0")

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        help="Available management commands",
    )

    # status
    subparsers.add_parser("status", parents=[common], help="Display router hardware, firmware, and operating metrics")

    # pon
    subparsers.add_parser("pon", parents=[common], help="Display optical GPON laser diagnostics and power levels")

    # devices
    subparsers.add_parser("devices", parents=[common], help="List all active LAN and WLAN connected client devices")

    # wifi
    wifi_parser = subparsers.add_parser("wifi", parents=[common], help="Inspect or modify Wi-Fi SSIDs and passphrases")
    wifi_sub = wifi_parser.add_subparsers(dest="wifi_action")
    wifi_sub.add_parser("show", help="Display current 2.4GHz and 5GHz wireless settings")
    wifi_set = wifi_sub.add_parser("set", help="Update Wi-Fi SSID or password")
    wifi_set.add_argument("--band", "-b", required=True, choices=["2.4g", "5g", "2.4ghz", "5ghz"], help="Wireless band")
    wifi_set.add_argument("--ssid", "-s", default=None, help="New wireless network name (SSID)")
    wifi_set.add_argument("--password", "-w", default=None, help="New WPA2-PSK passphrase (8-63 chars)")

    # backup
    backup_parser = subparsers.add_parser("backup", parents=[common], help="Export and download configuration backup (XML)")
    backup_parser.add_argument("output", nargs="?", default="tenda_backup.xml", help="Destination file path")

    # ping
    ping_parser = subparsers.add_parser("ping", parents=[common], help="Run a diagnostic ping from the router to an external host")
    ping_parser.add_argument("target", help="IP address or domain to ping (e.g. 1.1.1.1 or google.com)")

    # reboot
    subparsers.add_parser("reboot", parents=[common], help="Trigger a safe router restart")

    # --- Super Admin Commands ---
    subparsers.add_parser("wan", parents=[common], help="Display SLT broadband multi-WAN interface profiles and VLANs")
    subparsers.add_parser("voip", parents=[common], help="Display SLT VoIP telephony and SIP registrar configuration (Super Admin)")
    subparsers.add_parser("acl", parents=[common], help="Display management service Access Control List (ACL) rules (Super Admin)")
    subparsers.add_parser("tr069", parents=[common], help="Display TR-069 Auto-Configuration Server (ACS) settings (Super Admin)")

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Credential negotiation
    username = args.username
    password = args.password
    if args.super or args.command in ("voip", "acl", "tr069"):
        if not username:
            username = os.getenv("TENDA_SUPER_USERNAME", "administrator")
        if not password:
            password = os.getenv("TENDA_SUPER_PASSWORD")
        if not password:
            if sys.stdin.isatty():
                import getpass
                password = getpass.getpass("Enter ISP Super Admin password: ")
            else:
                console.print(
                    "[bold red]Error:[/bold red] Super Admin credentials required for this command.\n"
                    "Provide via [cyan]--password <pass>[/cyan] or set the [cyan]TENDA_SUPER_PASSWORD[/cyan] environment variable.",
                    file=sys.stderr,
                )
                sys.exit(1)

    try:
        with TendaClient(
            host=args.host,
            username=username,
            password=password,
            timeout=args.timeout,
        ) as client:
            if args.command == "status":
                status = client.get_status()
                table = Table(title=f"Tenda HG7 System Status (Role: {client.role})", show_header=True, header_style="bold cyan")
                table.add_column("Metric", style="bold")
                table.add_column("Value", style="green")

                table.add_row("Device Model", status.device_name)
                table.add_row("Software Version", status.software_version)
                table.add_row("Hardware Version", status.hardware_version)
                table.add_row("System Uptime", status.uptime)
                table.add_row("CPU Usage", f"{status.cpu_usage_pct:.1f}%")
                table.add_row("Memory Usage", f"{status.memory_usage_pct:.1f}%")
                table.add_row("LAN IP Address", status.lan_ip)
                table.add_row("LAN MAC Address", status.lan_mac.upper())
                table.add_row("DNS Resolvers", ", ".join(status.dns_servers))

                console.print(table)

            elif args.command == "pon":
                pon = client.get_pon_status()
                table = Table(title="GPON Optical Laser Telemetry", show_header=True, header_style="bold magenta")
                table.add_column("Telemetry Parameter", style="bold")
                table.add_column("Measurement", style="yellow")
                table.add_column("Status / Compliance", style="green")

                rx_status = "Good (Class B+ compliant)" if -28.0 <= pon.rx_power_dbm <= -8.0 else "Signal Warning"
                tx_status = "Normal (0.5 to 5.0 dBm)" if 0.5 <= pon.tx_power_dbm <= 5.0 else "Abnormal"

                table.add_row("ONU State", pon.onu_state, "O5 = Operational / Synchronized")
                table.add_row("Rx Optical Power", f"{pon.rx_power_dbm:.2f} dBm", rx_status)
                table.add_row("Tx Optical Power", f"{pon.tx_power_dbm:.2f} dBm", tx_status)
                table.add_row("Laser Temperature", f"{pon.temperature_c:.2f} °C", "Normal" if pon.temperature_c < 65.0 else "High")
                table.add_row("Internal Voltage", f"{pon.voltage_v:.3f} V", "Normal (3.3V bus)")
                table.add_row("Laser Bias Current", f"{pon.bias_current_ma:.2f} mA", "Normal")

                console.print(table)

            elif args.command == "devices":
                devices = client.get_connected_devices()
                table = Table(title=f"Connected Devices ({len(devices)} active)", show_header=True, header_style="bold blue")
                table.add_column("Interface", style="cyan")
                table.add_column("Hostname", style="bold white")
                table.add_column("MAC Address", style="yellow")
                table.add_column("IPv4 Address", style="green")
                table.add_column("IPv6 Address", style="magenta")

                for dev in devices:
                    table.add_row(
                        dev.interface_type,
                        dev.hostname,
                        dev.mac_address.upper(),
                        dev.ipv4_address or "--",
                        dev.ipv6_address or "--",
                    )

                console.print(table)

            elif args.command == "wifi":
                if args.wifi_action == "set":
                    client.set_wifi_config(band=args.band, ssid=args.ssid, password=args.password)
                    console.print(Panel(
                        f"[bold green]Successfully updated {args.band} Wi-Fi configuration![/bold green]\n"
                        f"SSID: {args.ssid or '[Unchanged]'}\n"
                        f"Passphrase: {'[Updated]' if args.password else '[Unchanged]'}",
                        title="Wi-Fi Mutation Applied",
                    ))
                else:
                    cfg_2g = client.get_wifi_config("2.4g")
                    cfg_5g = client.get_wifi_config("5g")

                    table = Table(title="Wireless Radio Configurations", show_header=True, header_style="bold green")
                    table.add_column("Band", style="bold")
                    table.add_column("Active SSID", style="bold white")
                    table.add_column("Channel", style="cyan")
                    table.add_column("Encryption", style="yellow")

                    table.add_row(cfg_5g.band, cfg_5g.ssid, str(cfg_5g.channel or "Auto"), cfg_5g.encryption)
                    table.add_row(cfg_2g.band, cfg_2g.ssid, str(cfg_2g.channel or "Auto"), cfg_2g.encryption)

                    console.print(table)

            elif args.command == "backup":
                dest = client.backup_config(args.output)
                size_kb = dest.stat().st_size / 1024
                console.print(Panel(
                    f"[bold green]Configuration backup exported successfully![/bold green]\n"
                    f"Saved to: [cyan]{dest.resolve()}[/cyan] ({size_kb:.1f} KB)",
                    title="Backup Export Complete",
                ))

            elif args.command == "ping":
                console.print(f"[yellow]Sending 4 ICMP ping packets to {args.target} from router...[/yellow]")
                res = client.ping(args.target)
                table = Table(title=f"Ping Diagnostic: {res.target}", show_header=True, header_style="bold cyan")
                table.add_column("Metric", style="bold")
                table.add_column("Result", style="green")

                table.add_row("Target Host", res.target)
                table.add_row("Packets Transmitted", str(res.transmitted))
                table.add_row("Packets Received", str(res.received))
                table.add_row("Packet Loss", f"{res.packet_loss_pct:.1f}%")

                console.print(table)

            elif args.command == "reboot":
                confirm = input("Are you sure you want to reboot the Tenda HG7 router? (y/N): ")
                if confirm.lower() == "y":
                    client.reboot()
                    console.print("[bold yellow]Reboot command dispatched. Router is restarting...[/bold yellow]")
                else:
                    console.print("[dim]Reboot cancelled.[/dim]")

            # Super Admin commands
            elif args.command == "wan":
                profiles = client.get_wan_profiles()
                table = Table(title="SLT Multi-WAN Connection Profiles", show_header=True, header_style="bold red")
                table.add_column("Interface", style="bold cyan")
                table.add_column("VLAN ID", style="yellow")
                table.add_column("Type", style="magenta")
                table.add_column("Protocol", style="green")
                table.add_column("IP Address", style="bold white")
                table.add_column("Gateway", style="dim")
                table.add_column("Status", style="bold green")

                for p in profiles:
                    table.add_row(
                        p.interface_name,
                        str(p.vlan_id or "--"),
                        p.connection_type,
                        p.protocol,
                        p.ipv4_address or "--",
                        p.gateway or "--",
                        p.status,
                    )

                console.print(table)

            elif args.command == "voip":
                voip = client.get_voip_config()
                table = Table(title="SLT Landline VoIP SIP Telephony Configuration", show_header=True, header_style="bold magenta")
                table.add_column("SIP Parameter", style="bold")
                table.add_column("Value", style="green")

                table.add_row("Phone Number", voip.phone_number)
                table.add_row("Display Name", voip.display_name)
                table.add_row("SIP Account Login ID", voip.sip_account)
                table.add_row("SIP Proxy Server", f"{voip.sip_proxy}:{voip.sip_port}")
                table.add_row("SIP Domain", voip.domain)
                table.add_row("Outbound Proxy", voip.outbound_proxy or "--")
                table.add_row("RTP Media Port", str(voip.rtp_port))

                console.print(table)

            elif args.command == "acl":
                rules = client.get_acl_rules()
                table = Table(title="Management Service Access Control Lists (ACL)", show_header=True, header_style="bold yellow")
                table.add_column("Interface", style="bold cyan")
                table.add_column("State", style="bold")
                table.add_column("Authorized IP Range", style="yellow")
                table.add_column("Exposed Services", style="green")
                table.add_column("Ports", style="dim")

                for r in rules:
                    state_style = "green" if r.state == "Enable" else "dim"
                    table.add_row(
                        r.interface_type,
                        f"[{state_style}]{r.state}[/{state_style}]",
                        r.ip_range or "All (Unrestricted)",
                        ", ".join(r.services),
                        ", ".join(r.ports),
                    )

                console.print(table)

            elif args.command == "tr069":
                tr = client.get_tr069_config()
                table = Table(title="TR-069 CPE WAN Management Protocol (CWMP)", show_header=True, header_style="bold blue")
                table.add_column("ACS Parameter", style="bold")
                table.add_column("Value", style="green")

                table.add_row("Auto-Configuration Server (ACS)", tr.acs_url)
                table.add_row("ACS Username", tr.acs_username)
                table.add_row("Periodic Inform", "Enabled" if tr.periodic_inform else "Disabled")
                table.add_row("Inform Interval", f"{tr.inform_interval_sec} seconds ({tr.inform_interval_sec // 3600} hours)")
                table.add_row("Connection Request Port", str(tr.connection_request_port))
                table.add_row("Connection Request Path", tr.connection_request_path)
                table.add_row("Connection Request Username", tr.connection_request_username or "--")

                console.print(table)

    except TendaError as e:
        console.print(f"[bold red]Router Error:[/bold red] {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Aborted by user.[/dim]")
        sys.exit(130)


if __name__ == "__main__":
    main()
