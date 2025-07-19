"""
monitor.py
----------
Monitor a specific WiFi SSID and print signal details every second.

Features:
- If connected to the SSID, print signal, freq, channel, band, and error rates (retries, invalid beacon/crypt/frag).
- If not connected, print signal, freq, channel, and band.
- For macOS, uses system_profiler and networksetup (error rates are mocked for now).

Author: Jason A. Cox
18 July 2025
github.com/jasonacox/tinywifi
"""
import time
import subprocess
from colorama import Fore, Style
from .scan import parse_system_profiler_output, channel_to_freq, get_wifi_networks


def monitor_ssid(ssid, timeout=10, count=10, delay=1):
    """
    Monitor a specific SSID, printing signal details in a table every delay seconds, up to count rows.
    Args:
        ssid (str): SSID to monitor.
        timeout (int): Duration in seconds to monitor (unused if count is set).
        count (int): Number of rows to print in the table.
        delay (int): Delay in seconds between each row.
    """
    # Use common scan function to get all networks
    networks_dict = get_wifi_networks(timeout)
    connected_id = networks_dict.get('current')

    # If no SSID specified, prompt user to pick one
    ssid_id = None
    freq = None
    if not ssid:
        print(f"{Fore.YELLOW}Available WiFi Networks:{Style.RESET_ALL}")
        ssid_ids = [k for k in networks_dict.keys() if k != 'current']
        for idx, unique_id in enumerate(ssid_ids, 1):
            net = networks_dict[unique_id]
            star = f"{Fore.YELLOW}*{Style.RESET_ALL}" if unique_id == connected_id else " "
            print(f"{star} [{idx}] {net['ssid']} (Freq: {net['freq']}, Channel: {net['channel']}, Band: {net['band']})")
        choice = input(f"Select network to monitor [1-{len(ssid_ids)}]: ")
        try:
            choice_idx = int(choice) - 1
            ssid_id = ssid_ids[choice_idx]
            ssid = networks_dict[ssid_id]['ssid']
            freq = networks_dict[ssid_id]['freq']
        except (ValueError, IndexError):
            print(f"{Fore.RED}Invalid selection.{Style.RESET_ALL}")
            return
    else:
        # Find all matching SSIDs
        matches = [uid for uid, net in networks_dict.items() if net['ssid'] == ssid and uid != 'current']
        if not matches:
            print(f"{Fore.RED}SSID '{ssid}' not found!{Style.RESET_ALL}")
            return
        if len(matches) > 1:
            print(f"{Fore.YELLOW}Multiple networks found for SSID '{ssid}':{Style.RESET_ALL}")
            for idx, unique_id in enumerate(matches, 1):
                net = networks_dict[unique_id]
                star = f"{Fore.YELLOW}*{Style.RESET_ALL}" if unique_id == connected_id else " "
                print(f"{star} [{idx}] {net['ssid']} (Freq: {net['freq']}, Channel: {net['channel']}, Band: {net['band']})")
            choice = input(f"Select network to monitor [1-{len(matches)}]: ")
            try:
                choice_idx = int(choice) - 1
                ssid_id = matches[choice_idx]
                ssid = networks_dict[ssid_id]['ssid']
                freq = networks_dict[ssid_id]['freq']
            except (ValueError, IndexError):
                print(f"{Fore.RED}Invalid selection.{Style.RESET_ALL}")
                return
        else:
            ssid_id = matches[0]
            freq = networks_dict[ssid_id]['freq']

    print(f"{Fore.YELLOW}Monitoring SSID '{ssid}' ({count} samples, {delay}s interval)...{Style.RESET_ALL}")
    print_monitor_table_header()
    for i in range(count):
        try:
            # Refresh scan each time for live stats
            networks_dict = get_wifi_networks(timeout=2)
            net = networks_dict.get(ssid_id)
            if net:
                # Simulate connection info (mocked)
                connected = True
                retries = invalid_beacon = invalid_crypt = invalid_frag = 0
                row = {
                    "signal": net["rssi"],
                    "freq": net["freq"],
                    "channel": net["channel"],
                    "band": net["band"],
                    "connected": connected,
                    "retries": retries,
                    "invalid_beacon": invalid_beacon,
                    "invalid_crypt": invalid_crypt,
                    "invalid_frag": invalid_frag,
                }
            else:
                row = {"signal": "N/A", "freq": "N/A", "channel": "N/A", "band": "N/A", "connected": False, "retries": "-", "invalid_beacon": "-", "invalid_crypt": "-", "invalid_frag": "-"}
        except Exception as e:
            print(f"{Fore.RED}Error monitoring WiFi: {e}{Style.RESET_ALL}")
            row = {"signal": "ERR", "freq": "ERR", "channel": "ERR", "band": "ERR", "connected": False, "retries": "-", "invalid_beacon": "-", "invalid_crypt": "-", "invalid_frag": "-"}
        print_monitor_table_row(i+1, row)
        time.sleep(delay)

def print_monitor_table_header():
    """
    Print the header for the monitor table.
    """
    print(f"{Fore.CYAN}{'Sample':<8} {'Signal':<8} {'Freq':<8} {'Channel':<8} {'Band':<7} {'Conn':<6} {'Retries':<8} {'InvBeacon':<10} {'InvCrypt':<9} {'InvFrag':<8}{Style.RESET_ALL}")

def print_monitor_table_row(i, row):
    """
    Print a single row for the monitor table.
    """
    band_color = Fore.LIGHTGREEN_EX if row["band"] == "2.4GHz" else Fore.LIGHTMAGENTA_EX
    conn_color = Fore.GREEN if row["connected"] else Fore.RED
    print(f"{Fore.WHITE}{i:<8} {row['signal']:<8} {row['freq']:<8} {row['channel']:<8} {band_color}{row['band']:<7} {conn_color}{str(row['connected']):<6} {Fore.YELLOW}{row['retries']:<8} {row['invalid_beacon']:<10} {row['invalid_crypt']:<9} {row['invalid_frag']:<8}{Style.RESET_ALL}")


def get_current_network_info(output, ssid):
    """
    Parse current network info for the given SSID from system_profiler output.
    Returns dict with error rates (mocked for now).
    """
    in_current = False
    info = {}
    for line in output.splitlines():
        if "Current Network Information:" in line:
            in_current = True
            continue
        if in_current:
            if ssid is not None and line.strip().startswith(ssid + ":"):
                info["connected"] = True
            if "Signal / Noise:" in line:
                info["signal"] = (
                    line.split(":", 1)[1]
                    .strip()
                    .split("/")[0]
                    .strip()
                    .replace(" dBm", "")
                )
            if "Channel:" in line:
                info["channel"] = line.split(":", 1)[1].strip().split(" ")[0]
                info["freq"] = channel_to_freq(info["channel"])
                info["band"] = (
                    "2.4GHz"
                    if info["channel"].isdigit() and 1 <= int(info["channel"]) <= 14
                    else "5GHz"
                )
            # Mock error rates
            info["retries"] = 0
            info["invalid_beacon"] = 0
            info["invalid_crypt"] = 0
            info["invalid_frag"] = 0
            if line.strip() == "":
                break
    return info if "connected" in info else None


def print_wifi_status(net, connected, info):
    """
    Print WiFi status for the SSID, including error rates if connected.
    """
    print(
        f"{Fore.CYAN}SSID: {net['ssid']:<32} Signal: {net['rssi']:<8} Freq: {net['freq']:<8} Channel: {net['channel']:<8} Band: {net['band']:<7}{Style.RESET_ALL}"
    )
    if connected and info:
        print(
            f"{Fore.LIGHTRED_EX}Error Rates: Retries={info['retries']} InvalidBeacon={info['invalid_beacon']} InvalidCrypt={info['invalid_crypt']} InvalidFrag={info['invalid_frag']}{Style.RESET_ALL}"
        )
