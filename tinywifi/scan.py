#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WiFi scanning and analysis functions for TinyWiFi CLI tool.

Features:
- Scans for WiFi SSIDs and reports signal, frequency, channel, and band (2.4GHz/5GHz).
- Uses macOS system_profiler for cross-platform compatibility.
- Colorized table output using colorama.
- Functions for converting between channel and frequency.

Author: Jason A. Cox
17 July 2025
github.com/jasonacox/tinywifi
"""

import re
import subprocess
import time
import platform

from colorama import Fore, Style, init

init(autoreset=True)

def get_wifi_networks(timeout=5, os="macos"):
    """
    Scan for WiFi networks and return a dict of unique networks keyed by SSID+freq, and the unique_id of the currently connected SSID.
    Args:
        timeout (int): Total time in seconds to scan (multiple scans).
    Returns:
        Tuple[Dict[str, dict], str]: Dict of network info keyed by unique_id ("SSID_freq"), and the connected unique_id (or None).
    """
    all_networks = {}
    scans = max(1, timeout // 2)
    connected_unique_id = None
    if os == "macos":
        # macOS logic
        for i in range(scans):
            try:
                result = subprocess.run(
                    ["system_profiler", "SPAirPortDataType"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                networks = parse_system_profiler_output(result.stdout)
                for net in networks:
                    unique_id = f"{net['ssid']}_{net['freq']}"
                    all_networks[unique_id] = net
                # Only on first scan, parse connected SSID/channel
                if i == 0:
                    in_current = False
                    ssid = None
                    channel = None
                    for line in result.stdout.splitlines():
                        if "Current Network Information:" in line:
                            in_current = True
                            continue
                        if in_current:
                            line = line.strip()
                            if line.endswith(":") and not line.startswith("PHY Mode"):
                                ssid = line[:-1]
                            if "Channel:" in line:
                                channel = line.split(":", 1)[1].strip().split(" ")[0]
                            if ssid and channel:
                                freq = channel_to_freq(channel)
                                connected_unique_id = f"{ssid}_{freq}"
                                in_current = False  # Unset after recording
                            if line == "":
                                break
            except Exception as e:
                print(f"{Fore.RED}Error scanning WiFi: {e}{Style.RESET_ALL}")
            if i < scans - 1:
                time.sleep(2)
        all_networks['current'] = connected_unique_id
        return all_networks
    elif os == "linux":
        # Linux logic using nmcli
        for i in range(scans):
            try:
                # Scan for WiFi networks
                scan_result = subprocess.run(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL,CHAN,FREQ", "device", "wifi", "list"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                # Get current connected SSID
                conn_result = subprocess.run(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID,CHAN,FREQ", "device", "wifi"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                connected_unique_id = None
                for line in conn_result.stdout.splitlines():
                    fields = line.strip().split(":")
                    if len(fields) >= 4 and fields[0] == "yes":
                        ssid = fields[1]
                        channel = fields[2]
                        freq = fields[3]
                        connected_unique_id = f"{ssid}_{freq}"
                        break
                for line in scan_result.stdout.splitlines():
                    fields = line.strip().split(":")
                    if len(fields) >= 4:
                        ssid = fields[0]
                        signal = int(fields[1]) if fields[1].isdigit() else -100
                        channel = fields[2]
                        freq = fields[3]
                        band = "2.4GHz" if freq and freq.startswith("2") else "5GHz"
                        unique_id = f"{ssid}_{freq}"
                        all_networks[unique_id] = {
                            "ssid": ssid,
                            "rssi": signal,
                            "channel": channel,
                            "freq": freq,
                            "band": band,
                        }
            except Exception as e:
                print(f"{Fore.RED}Error scanning WiFi: {e}{Style.RESET_ALL}")
            if i < scans - 1:
                time.sleep(2)
        all_networks['current'] = connected_unique_id
        return all_networks
    elif os == "windows":
        # Windows logic (placeholder)
        raise NotImplementedError("Windows WiFi scanning not implemented yet.")
    else:
        raise ValueError(f"Unknown OS: {os}")

def scan(timeout=5):
    """
    Scan WiFi networks on macOS using system_profiler.
    Runs multiple scans over the given timeout (seconds) for better SSID coverage.
    Returns a list of unique networks found.
    Args:
        timeout (int): Total time in seconds to scan (multiple scans).
    Returns:
        List[dict]: List of network info dicts (ssid, rssi, channel, freq, band).
    """
    print(f"{Fore.YELLOW}Scanning for WiFi networks...{Style.RESET_ALL}")
    # Detect OS
    sys_os = platform.system().lower()
    if sys_os.startswith("darwin") or sys_os == "macos":
        os_arg = "macos"
    elif sys_os == "linux":
        os_arg = "linux"
    elif sys_os == "windows":
        os_arg = "windows"
    else:
        print(f"{Fore.RED}Unsupported OS: {sys_os}{Style.RESET_ALL}")
        return []
    networks_dict = get_wifi_networks(timeout, os=os_arg)
    current_id = networks_dict.get('current')
    if not networks_dict:
        print(f"{Fore.RED}No WiFi networks found.{Style.RESET_ALL}")
        return []
    print(f"{Fore.GREEN}Found {len(networks_dict) - 1} networks.{Style.RESET_ALL}")
    # Print current connected SSID with name, channel, and frequency
    if current_id:
        current_net = networks_dict.get(current_id, {})
        print(f"{Fore.CYAN}Current connected SSID: {current_net.get('ssid', 'None')} (Channel: {current_net.get('channel', 'Unknown')}, Frequency: {current_net.get('freq', 'Unknown')}){Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}Current connected SSID: None{Style.RESET_ALL}")
    print()
    # Print colorized table with current SSID marked
    print_table(networks_dict, current_id)
    return [networks_dict[uid] for uid in networks_dict if uid != 'current']


def parse_system_profiler_output(output):
    """
    Parse output from 'system_profiler SPAirPortDataType' for WiFi networks.
    Extracts SSID, channel, signal, frequency, and band from the 'Other Local Wi-Fi Networks' section.
    Args:
        output (str): Raw output from system_profiler.
    Returns:
        List[dict]: List of network info dicts.
    """
    networks = []
    in_other_networks = False
    ssid = None
    channel = None
    signal = None
    freq = None
    for line in output.splitlines():
        line = line.rstrip()
        if "Other Local Wi-Fi Networks:" in line:
            in_other_networks = True
            continue
        if in_other_networks:
            if not line.strip():
                ssid = channel = signal = freq = None
                continue
            if not line.startswith(" " * 14):
                # New SSID
                ssid = line.strip().rstrip(":")
            elif "Channel:" in line:
                channel = line.split(":", 1)[1].strip().split(" ")[0]
            elif "Signal / Noise:" in line:
                signal = (
                    line.split(":", 1)[1]
                    .strip()
                    .split("/")[0]
                    .strip()
                    .replace(" dBm", "")
                )
            elif "(2GHz" in line or "(5GHz" in line:
                # Try to extract frequency from channel line, e.g. 'Channel: 100 (5GHz, 80MHz)'
                freq_match = re.search(r"\((\d+)GHz", line)
                if freq_match:
                    ghz = int(freq_match.group(1))
                    if channel:
                        try:
                            ch = int(channel)
                            freq = 2407 + ch * 5 if ghz == 2 else 5000 + ch * 5
                        except Exception:
                            freq = None
            if ssid and signal and (channel or freq):
                if not channel and freq:
                    channel = freq_to_channel(freq)
                freq_val = channel_to_freq(channel) if channel else freq
                band = (
                    "2.4GHz"
                    if channel and channel.isdigit() and 1 <= int(channel) <= 14
                    else "5GHz"
                )
                networks.append(
                    {
                        "ssid": ssid,
                        "rssi": int(signal),
                        "channel": channel if channel else "Unknown",
                        "freq": freq_val if freq_val else "Unknown",
                        "band": band,
                    }
                )
                ssid = channel = signal = freq = None
        # End parsing if we hit another section
        if in_other_networks and (
            line.strip().endswith("Networks:") and not line.strip().startswith("Other")
        ):
            break
    return networks


def freq_to_channel(freq):
    """
    Convert frequency (MHz) to WiFi channel number.
    Args:
        freq (int or str): Frequency in MHz.
    Returns:
        str: Channel number or 'Unknown'.
    """
    try:
        freq = int(freq)
        if 2412 <= freq <= 2472:
            return str((freq - 2407) // 5)
        elif 5180 <= freq <= 5825:
            return str((freq - 5000) // 5)
        else:
            return "Unknown"
    except Exception:
        return "Unknown"


def channel_to_freq(channel):
    """
    Convert WiFi channel number to frequency in MHz.
    Args:
        channel (int or str): WiFi channel number.
    Returns:
        int or str: Frequency in MHz or 'Unknown'.
    """
    try:
        ch = int(channel)
        if 1 <= ch <= 14:
            # 2.4 GHz band
            return 2407 + ch * 5
        elif 36 <= ch <= 64:
            # 5 GHz lower band
            return 5000 + ch * 5
        elif 100 <= ch <= 144:
            # 5 GHz middle band
            return 5000 + ch * 5
        elif 149 <= ch <= 165:
            # 5 GHz upper band
            return 5000 + ch * 5
        else:
            return "Unknown"
    except Exception:
        return "Unknown"


def print_table(networks_dict, current_id=None):
    """
    Print a colorized table of WiFi networks.
    Args:
        networks_dict (dict): Dictionary of network info keyed by unique_id.
        current_id (str): Unique ID of the currently connected SSID.
    """
    if not networks_dict:
        print(f"{Fore.RED}No WiFi networks found.{Style.RESET_ALL}")
        return

    # Print header
    print(f"{Fore.CYAN}{'SSID':<32} {'Signal':<8} {'Freq':<8} {'Channel':<8} {'Band':<7} {'State':<8}{Style.RESET_ALL}")
    
    # Sort by best signal (highest RSSI)
    ssid_list = [k for k in networks_dict.keys() if k != 'current']
    ssid_list.sort(key=lambda k: networks_dict[k]['rssi'], reverse=True)

    for unique_id in ssid_list:
        net = networks_dict[unique_id]
        color = (
            Fore.GREEN
            if net["rssi"] > -60
            else (Fore.YELLOW if net["rssi"] > -80 else Fore.RED)
        )
        band_color = (
            Fore.LIGHTGREEN_EX if net["band"] == "2.4GHz" else Fore.LIGHTMAGENTA_EX
        )
        ssid_display = net['ssid']
        current = "Connected" if unique_id == current_id else ""
        print(
            f"{Fore.WHITE}{ssid_display:<32} {color}{net['rssi']:<8} {Fore.BLUE}{net['freq']:<8} {Fore.MAGENTA}{net['channel']:<8} {band_color}{net['band']:<7}{Style.RESET_ALL} {Fore.GREEN}{current:<8}{Style.RESET_ALL}"
        )
