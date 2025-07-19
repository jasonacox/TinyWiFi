"""
cli.py
-----
Command-line interface for TinyWiFi.

Features:
- scan: Scan for WiFi networks and display results in a colorized table.
- monitor: (mocked) Monitor a specific SSID for a given timeout.
- Uses argparse for flexible command parsing and help output.

Author: Jason A. Cox
17 July 2025
github.com/jasonacox/tinywifi
"""
import argparse
import platform
import sys
from .scan import scan, print_table
from .monitor import monitor_ssid


def main():
    parser = argparse.ArgumentParser(
        description="TinyWiFi: WiFi signal analysis tool (cross-platform)",
        usage="python -m tinywifi {scan,monitor} [options]",
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan for WiFi networks")
    scan_parser.add_argument(
        "--timeout", type=int, default=5, help="Timeout in seconds for scan"
    )

    monitor_parser = subparsers.add_parser("monitor", help="Monitor a specific SSID")
    monitor_parser.add_argument("ssid", type=str, help="SSID to monitor")
    monitor_parser.add_argument(
        "--timeout", type=int, default=5, help="Timeout in seconds for monitor"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Platform check removed; scan() auto-detects OS

    if args.command == "scan":
        scan(timeout=args.timeout)
    elif args.command == "monitor":
        monitor_ssid(args.ssid, timeout=args.timeout)


if __name__ == "__main__":
    main()
