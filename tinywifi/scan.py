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
import os

from colorama import Fore, Style, init

init(autoreset=True)

def get_wifi_networks(timeout=5, target_os="macos"):
    """
    Scan for WiFi networks and return a dict of unique networks keyed by SSID+freq, and the unique_id of the currently connected SSID.
    Args:
        timeout (int): Total time in seconds to scan (multiple scans).
        target_os (str): Target operating system ("macos", "linux", "windows").
    Returns:
        Tuple[Dict[str, dict], str]: Dict of network info keyed by unique_id ("SSID_freq"), and the connected unique_id (or None).
    """
    all_networks = {}
    scans = max(1, timeout // 2)
    connected_unique_id = None
    if target_os == "macos":
        # macOS logic using system_profiler SPAirPortDataType
        for i in range(scans):
            try:
                result = subprocess.run(
                    ["system_profiler", "SPAirPortDataType"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                
                # Parse networks from system_profiler output
                networks = _parse_macos_networks(result.stdout)
                
                # Add networks to our collection
                for net in networks:
                    unique_id = f"{net['ssid']}_{net['freq']}"
                    all_networks[unique_id] = net
                
                # Only on first scan, find the currently connected network
                if i == 0:
                    connected_unique_id = _parse_macos_connected_network(result.stdout)
                    
                    # Also try to extract rate information for the connected network
                    if connected_unique_id and connected_unique_id in all_networks:
                        rate_info = _extract_connected_rate(result.stdout)
                        if rate_info:
                            all_networks[connected_unique_id]['rate'] = rate_info + " Mbps"
                    
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                print(f"{Fore.RED}Error scanning WiFi: {e}{Style.RESET_ALL}")
            
            if i < scans - 1:
                time.sleep(2)
                
        all_networks['current'] = connected_unique_id
        return all_networks
    elif target_os == "linux":
        # Linux logic using multiple tools for comprehensive data
        connected_unique_id = None
        for i in range(scans):
            try:
                # First try iwlist for detailed signal information
                networks_detailed = _get_linux_iwlist_networks()
                
                # Then get nmcli data for additional info and active connections
                networks_nmcli = _get_linux_nmcli_networks()
                
                # Merge the data sources
                for nmcli_net in networks_nmcli:
                    unique_id = f"{nmcli_net['ssid']}_{nmcli_net['freq']}"
                    
                    # Look for matching network in iwlist data for enhanced signal info
                    iwlist_match = None
                    for iwlist_net in networks_detailed:
                        if (iwlist_net['ssid'] == nmcli_net['ssid'] and 
                            abs(int(iwlist_net['freq']) - int(nmcli_net['freq'])) < 10):  # Allow small freq differences
                            iwlist_match = iwlist_net
                            break
                    
                    # Combine data from both sources
                    combined_net = nmcli_net.copy()
                    if iwlist_match:
                        # Use iwlist data for signal, noise if available
                        if iwlist_match.get('rssi') != -100:
                            combined_net['rssi'] = iwlist_match['rssi']
                        if iwlist_match.get('noise') is not None:
                            combined_net['noise'] = iwlist_match['noise']
                        if iwlist_match.get('snr') is not None:
                            combined_net['snr'] = iwlist_match['snr']
                    
                    all_networks[unique_id] = combined_net
                    
                    # Check if this is the active connection
                    if nmcli_net.get('active'):
                        connected_unique_id = unique_id
                        
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                print(f"{Fore.RED}Error scanning WiFi: {e}{Style.RESET_ALL}")
            
            if i < scans - 1:
                time.sleep(2)
                
        all_networks['current'] = connected_unique_id
        return all_networks
    elif target_os == "windows":
        # Windows logic (placeholder)
        raise NotImplementedError("Windows WiFi scanning not implemented yet.")
    else:
        raise ValueError(f"Unknown OS: {target_os}")

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
    networks_dict = get_wifi_networks(timeout, target_os=os_arg)
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
                        except (ValueError, TypeError):
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
    except (ValueError, TypeError):
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
            # 2.4 GHz band - more accurate calculation
            if ch == 14:
                return 2484  # Special case for channel 14
            else:
                return 2412 + (ch - 1) * 5
        elif 36 <= ch <= 64:
            # 5 GHz lower band
            return 5000 + ch * 5
        elif 100 <= ch <= 144:
            # 5 GHz middle band (DFS channels)
            return 5000 + ch * 5
        elif 149 <= ch <= 165:
            # 5 GHz upper band
            return 5000 + ch * 5
        else:
            return "Unknown"
    except (ValueError, TypeError):
        return "Unknown"

def print_table(networks_dict, current_id=None):
    """
    Print a colorized table of WiFi networks.
    Args:
        networks_dict (dict): Dictionary of network info keyed by unique_id.
        current_id (str): Unique ID of the currently connected SSID.
    """
    if not networks_dict or all(k == 'current' for k in networks_dict):
        print(f"{Fore.RED}No WiFi networks found.{Style.RESET_ALL}")
        return

    # Sort by best signal (highest RSSI)
    ssid_list = sorted(
        [k for k in networks_dict.keys() if k != 'current'],
        key=lambda k: networks_dict[k].get('rssi', -100), 
        reverse=True
    )

    # Check if optional data is available
    show_bssid = any(networks_dict[k].get('bssid', '') for k in ssid_list)
    show_noise = any(networks_dict[k].get('noise') is not None and networks_dict[k].get('noise') != -100 for k in ssid_list)
    show_snr = any(networks_dict[k].get('snr') is not None for k in ssid_list)

    # Build header based on available data
    header_parts = [('SSID', 24)]
    if show_bssid:
        header_parts.append(('BSSID', 18))
    header_parts.append(('Signal', 14))
    if show_noise:
        header_parts.append(('Noise', 8))
    if show_snr:
        header_parts.append(('SNR', 8))
    header_parts.extend([
        ('Freq', 8),
        ('Channel', 8),
        ('Band', 7),
        ('Mode', 7),
        ('Rate', 10),
        ('Security', 12),
        ('State', 8)
    ])
    
    # Print the header
    header_str = "".join(f"{name:<{width}} " for name, width in header_parts)
    print(f"{Fore.CYAN}{header_str.rstrip()}{Style.RESET_ALL}")

    for unique_id in ssid_list:
        net = networks_dict[unique_id]
        signal_val = net.get('signal')
        rssi = net.get('rssi', -100)
        
        # Determine signal color based on strength
        # 	Signal strength: -58 dBm → Strong. (Closer to 0 is better; -30 is excellent, -60 is good, -70 is fair.)
	    #   Noise level: -89 dBm → Low interference. (More negative is better.)
	    #   SNR (Signal-to-Noise Ratio): 31 dB → Very good connection.
        if (signal_val is not None and signal_val >= 65) or rssi > -60:
            color = Fore.GREEN
        elif (signal_val is not None and signal_val >= 60) or (-66 < rssi <= -60):
            color = Fore.YELLOW
        else:
            color = Fore.RED
            
        # Format signal display - only show dBm if we have real values
        if rssi != -100:
            if signal_val is not None:
                signal_display = f"{signal_val}% ({rssi} dB)"
            else:
                signal_display = f"{rssi} dB"
        elif signal_val is not None:
            signal_display = f"{signal_val}%"
        else:
            signal_display = "--"
        
        # Format other fields
        ssid_raw = net.get('ssid', '')
        ssid_display = ssid_raw[:21] + '...' if len(ssid_raw) > 24 else ssid_raw
        ssid_color = Fore.GREEN if unique_id == current_id else Fore.WHITE
        
        security_val = net.get('security', '')
        if security_val.endswith('Personal'):
            security_val = security_val.replace('Personal', '').strip()
        security_val = security_val[:12]
        
        band_color = Fore.LIGHTGREEN_EX if net.get("band") == "2.4GHz" else Fore.LIGHTMAGENTA_EX
        current = "Connected" if unique_id == current_id else ""
        
        # Format noise and SNR if available
        noise_val = net.get('noise')
        snr_val = net.get('snr')
        
        if noise_val is not None and noise_val != -100:
            noise_display = f"{noise_val} dB"
            noise_color = Fore.LIGHTBLACK_EX
        else:
            noise_display = "--"
            noise_color = Fore.LIGHTBLACK_EX
            
        if snr_val is not None:
            snr_display = f"{snr_val} dB"
            # Color SNR based on quality: >25 excellent, 15-25 good, <15 poor
            if snr_val > 25:
                snr_color = Fore.GREEN
            elif snr_val >= 15:
                snr_color = Fore.YELLOW
            else:
                snr_color = Fore.RED
        else:
            snr_display = "--"
            snr_color = Fore.LIGHTBLACK_EX
        
        # Build the row based on available data
        row_parts = [(ssid_color, ssid_display, 24)]
        if show_bssid:
            row_parts.append((Fore.LIGHTBLACK_EX, net.get('bssid',''), 18))
        row_parts.append((color, signal_display, 14))
        if show_noise:
            row_parts.append((noise_color, noise_display, 8))
        if show_snr:
            row_parts.append((snr_color, snr_display, 8))
        row_parts.extend([
            (Fore.BLUE, str(net.get('freq','')), 8),
            (Fore.MAGENTA, str(net.get('channel','')), 8),
            (band_color, net.get('band',''), 7),
            (Fore.CYAN, net.get('mode',''), 7),
            (Fore.YELLOW, net.get('rate',''), 10),
            (Fore.LIGHTWHITE_EX, security_val, 12),
            (Fore.GREEN, current, 8)
        ])
        
        # Print the row
        row_str = "".join(f"{color}{value:<{width}} " for color, value, width in row_parts)
        print(f"{row_str.rstrip()}{Style.RESET_ALL}")


def _parse_macos_networks(output):
    """
    Parse networks from the 'Other Local Wi-Fi Networks' section of system_profiler output.
    
    Args:
        output (str): Raw output from system_profiler SPAirPortDataType
        
    Returns:
        List[dict]: List of network dictionaries
    """
    networks = []
    lines = output.splitlines()
    
    # Find the start of "Other Local Wi-Fi Networks" section
    in_networks_section = False
    current_network = {}
    
    for line in lines:
        line = line.rstrip()
        
        if "Other Local Wi-Fi Networks:" in line:
            in_networks_section = True
            continue
            
        if not in_networks_section:
            continue
            
        # Stop if we hit another major section
        if line and not line.startswith(" ") and ":" in line and not line.startswith("            "):
            break
            
        # Empty line or new network starts
        if not line.strip():
            if current_network and current_network.get('ssid'):
                networks.append(_finalize_network(current_network))
            current_network = {}
            continue
            
        # Network name (SSID) - starts at column 12, ends with ":"
        if line.startswith("            ") and not line.startswith("              ") and line.endswith(":"):
            if current_network and current_network.get('ssid'):
                networks.append(_finalize_network(current_network))
            current_network = {'ssid': line.strip()[:-1]}  # Remove the trailing ":"
            continue
            
        # Network properties - indented further
        if line.startswith("              ") and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            
            if key == "Channel":
                # Extract channel number and frequency band
                channel_match = re.search(r"(\d+)\s*\((\d+)GHz", value)
                if channel_match:
                    current_network['channel'] = channel_match.group(1)
                    ghz = int(channel_match.group(2))
                    current_network['freq'] = channel_to_freq(current_network['channel'])
                    current_network['band'] = f"{ghz}GHz" if ghz in [2, 5] else "Unknown"
                    
            elif key == "Signal / Noise":
                # Extract signal and noise values
                sig_noise = value.split("/")
                if len(sig_noise) >= 1:
                    signal_str = sig_noise[0].strip().replace(" dBm", "")
                    try:
                        current_network['rssi'] = int(signal_str)
                    except ValueError:
                        current_network['rssi'] = -100
                        
                if len(sig_noise) >= 2:
                    noise_str = sig_noise[1].strip().replace(" dBm", "")
                    try:
                        current_network['noise'] = int(noise_str)
                    except ValueError:
                        current_network['noise'] = -100
                        
            elif key == "Security":
                current_network['security'] = value
                
            elif key == "Network Type":
                current_network['mode'] = "Infra" if value.startswith("Infrastructure") else value
                
            elif key == "Transmit Rate":
                current_network['rate'] = value
                
    # Don't forget the last network
    if current_network and current_network.get('ssid'):
        networks.append(_finalize_network(current_network))
        
    return networks


def _parse_macos_connected_network(output):
    """
    Parse the currently connected network from system_profiler output.
    
    Args:
        output (str): Raw output from system_profiler SPAirPortDataType
        
    Returns:
        str or None: Unique ID of connected network (ssid_freq) or None
    """
    lines = output.splitlines()
    in_current_section = False
    ssid = None
    channel = None
    
    for line in lines:
        line = line.strip()
        
        if "Current Network Information:" in line:
            in_current_section = True
            continue
            
        if not in_current_section:
            continue
            
        # Stop if we hit "Other Local Wi-Fi Networks:" or empty line after getting data
        if "Other Local Wi-Fi Networks:" in line or (not line and ssid and channel):
            break
            
        # SSID is the first line after "Current Network Information:" that ends with ":"
        if line.endswith(":") and not any(x in line for x in ["PHY Mode", "Channel", "Country", "Network", "Security", "Signal", "Transmit", "MCS"]):
            ssid = line[:-1]  # Remove trailing ":"
            
        elif line.startswith("Channel:"):
            channel_info = line.split(":", 1)[1].strip()
            channel_match = re.search(r"(\d+)", channel_info)
            if channel_match:
                channel = channel_match.group(1)
                
        # Once we have both SSID and channel, we can create the unique ID
        if ssid and channel:
            freq = channel_to_freq(channel)
            return f"{ssid}_{freq}"
            
    return None


def _extract_connected_rate(output):
    """
    Extract the transmit rate from the current network information section.
    
    Args:
        output (str): Raw output from system_profiler SPAirPortDataType
        
    Returns:
        str or None: Transmit rate or None if not found
    """
    lines = output.splitlines()
    in_current_section = False
    
    for line in lines:
        line = line.strip()
        
        if "Current Network Information:" in line:
            in_current_section = True
            continue
            
        if not in_current_section:
            continue
            
        # Stop if we hit "Other Local Wi-Fi Networks:" 
        if "Other Local Wi-Fi Networks:" in line:
            break
            
        if line.startswith("Transmit Rate:"):
            rate_info = line.split(":", 1)[1].strip()
            return rate_info
            
    return None


def _finalize_network(network_dict):
    """
    Finalize a network dictionary with calculated fields and defaults.
    
    Args:
        network_dict (dict): Partial network dictionary
        
    Returns:
        dict: Complete network dictionary
    """
    # Calculate signal percentage from RSSI and noise if available
    rssi = network_dict.get('rssi', -100)
    noise = network_dict.get('noise', -100)
    snr = None
    
    if rssi != -100 and noise != -100:
        snr = rssi - noise
        signal_percent = min(100, max(0, int((snr + 100) * 0.5)))
    else:
        # Fallback: simple RSSI to percentage conversion
        signal_percent = min(100, max(0, 2 * (rssi + 100)))
        
    # Set defaults for missing fields
    return {
        'ssid': network_dict.get('ssid', 'Unknown'),
        'bssid': network_dict.get('bssid', ''),  # macOS doesn't provide BSSID in system_profiler
        'rssi': rssi,
        'signal': signal_percent,
        'noise': network_dict.get('noise', None),
        'snr': snr,
        'channel': network_dict.get('channel', '--'),
        'freq': network_dict.get('freq', '--'),
        'band': network_dict.get('band', 'Unknown'),
        'mode': network_dict.get('mode', '--'),
        'rate': network_dict.get('rate', '--'),
        'security': network_dict.get('security', '--'),
    }


def _get_linux_iwlist_networks():
    """
    Get WiFi networks using iwlist scan for detailed signal information.
    
    Returns:
        List[dict]: List of network dictionaries with signal/noise data
    """
    networks = []
    try:
        # Try to find wireless interface
        result = subprocess.run(
            ["iwconfig"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        # Find wireless interface name
        interface = None
        for line in result.stdout.splitlines():
            if "IEEE 802.11" in line or "ESSID:" in line:
                interface = line.split()[0]
                break
        
        if not interface:
            return networks
        
        # Try iw scan first (newer and more reliable)
        networks_iw = _get_linux_iw_networks(interface)
        if networks_iw:
            return networks_iw
            
        # Fallback to iwlist scan
        scan_cmd = ["iwlist", interface, "scan"]
        try:
            scan_result = subprocess.run(scan_cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # Try with sudo if permission denied
            scan_cmd = ["sudo"] + scan_cmd
            scan_result = subprocess.run(scan_cmd, capture_output=True, text=True, check=True)
        
        # Parse iwlist output
        current_net = {}
        for line in scan_result.stdout.splitlines():
            line = line.strip()
            
            if line.startswith("Cell "):
                # New network entry
                if current_net and current_net.get('ssid'):
                    networks.append(current_net)
                current_net = {}
                
                # Extract BSSID and frequency from Cell line
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "Address:" and i + 1 < len(parts):
                        current_net['bssid'] = parts[i + 1]
                    elif part == "Frequency:" and i + 1 < len(parts):
                        freq_str = parts[i + 1]
                        if freq_str.endswith("GHz"):
                            freq_ghz = float(freq_str[:-3])
                            current_net['freq'] = str(int(freq_ghz * 1000))  # Convert to MHz
            
            elif line.startswith("Channel:"):
                current_net['channel'] = line.split(":")[1].strip()
                
            elif line.startswith("Quality=") or "Signal level=" in line:
                # More comprehensive signal parsing
                # Examples:
                # Quality=70/70  Signal level=-40 dBm  Noise level=-89 dBm
                # Quality=5/5  Signal level=1 dBm
                # Signal level=-42 dBm
                
                if "Signal level=" in line:
                    # Extract signal strength
                    signal_match = re.search(r"Signal level=(-?\d+(?:\.\d+)?)\s*dBm", line)
                    if signal_match:
                        try:
                            current_net['rssi'] = int(float(signal_match.group(1)))
                        except ValueError:
                            current_net['rssi'] = -100
                    else:
                        # Try alternative format: Signal level=-42 dBm
                        signal_match = re.search(r"Signal level=(-?\d+)", line)
                        if signal_match:
                            try:
                                current_net['rssi'] = int(signal_match.group(1))
                            except ValueError:
                                current_net['rssi'] = -100
                        
                if "Noise level=" in line:
                    # Extract noise floor
                    noise_match = re.search(r"Noise level=(-?\d+(?:\.\d+)?)\s*dBm", line)
                    if noise_match:
                        try:
                            noise_val = int(float(noise_match.group(1)))
                            current_net['noise'] = noise_val
                            
                            # Calculate SNR if we have both signal and noise
                            if current_net.get('rssi') and current_net['rssi'] != -100:
                                current_net['snr'] = current_net['rssi'] - noise_val
                        except ValueError:
                            pass
                        
            elif line.startswith("ESSID:"):
                essid = line.split(":", 1)[1].strip().strip('"')
                if essid and essid != "<hidden>":
                    current_net['ssid'] = essid
                    
            elif line.startswith("Mode:"):
                mode = line.split(":", 1)[1].strip()
                current_net['mode'] = "Infra" if mode == "Master" else mode
                
            elif "Encryption key:" in line:
                if "off" in line.lower():
                    current_net['security'] = "None"
                else:
                    current_net['security'] = "WPA/WPA2"  # Default assumption
        
        # Don't forget the last network
        if current_net and current_net.get('ssid'):
            networks.append(current_net)
            
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        # If iwlist fails, return empty list (we'll fall back to nmcli only)
        pass
        
    return networks


def _get_linux_iw_networks(interface):
    """
    Get WiFi networks using iw scan for detailed signal information.
    
    Args:
        interface (str): Wireless interface name
        
    Returns:
        List[dict]: List of network dictionaries with signal data
    """
    networks = []
    try:
        # Try iw scan command (more modern than iwlist)
        scan_cmd = ["iw", "dev", interface, "scan"]
        try:
            scan_result = subprocess.run(scan_cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # Try with sudo if permission denied
            scan_cmd = ["sudo"] + scan_cmd
            try:
                scan_result = subprocess.run(scan_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                return networks  # iw not available or failed
        
        # Parse iw scan output
        current_net = {}
        for line in scan_result.stdout.splitlines():
            line = line.strip()
            
            if line.startswith("BSS "):
                # New network entry
                if current_net and current_net.get('ssid'):
                    networks.append(current_net)
                current_net = {}
                
                # Extract BSSID and frequency from BSS line
                # Example: BSS 12:34:56:78:9a:bc(on wlan0) -- associated
                parts = line.split()
                if len(parts) > 1:
                    bssid_part = parts[1]
                    # Remove any parentheses and extra info
                    bssid = bssid_part.split('(')[0]
                    current_net['bssid'] = bssid
                    
            elif line.startswith("freq:"):
                freq_str = line.split(":")[1].strip()
                current_net['freq'] = freq_str
                
            elif line.startswith("signal:"):
                # Extract signal strength
                # Example: signal: -42.00 dBm
                signal_match = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", line)
                if signal_match:
                    try:
                        current_net['rssi'] = int(float(signal_match.group(1)))
                    except ValueError:
                        current_net['rssi'] = -100
                        
            elif line.startswith("SSID:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid and ssid != "--":
                    current_net['ssid'] = ssid
                    
            elif "capability:" in line.lower():
                # Extract basic security info from capability
                if "Privacy" in line:
                    current_net['security'] = "WPA/WPA2"  # Default assumption
                else:
                    current_net['security'] = "None"
        
        # Don't forget the last network
        if current_net and current_net.get('ssid'):
            networks.append(current_net)
            
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        # If iw fails, return empty list
        pass
        
    return networks


def _get_linux_nmcli_networks():
    """
    Get WiFi networks using nmcli for connection and basic info.
    
    Returns:
        List[dict]: List of network dictionaries from nmcli
    """
    networks = []
    try:
        # Check for root privileges
        is_root = (os.geteuid() == 0)
        nmcli_cmd = ["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,SIGNAL,CHAN,FREQ,MODE,RATE,SECURITY", "device", "wifi", "list"]
        if not is_root:
            try:
                scan_result = subprocess.run(nmcli_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                # Try with sudo if permission denied
                nmcli_cmd = ["sudo"] + nmcli_cmd
                scan_result = subprocess.run(nmcli_cmd, capture_output=True, text=True, check=True)
        else:
            scan_result = subprocess.run(nmcli_cmd, capture_output=True, text=True, check=True)
        
        for line in scan_result.stdout.splitlines():
            # nmcli escapes colons in BSSID and other fields as \:
            # Split only on unescaped colons
            fields = re.split(r'(?<!\\):', line.strip())
            # Unescape colons in fields
            fields = [f.replace('\\:', ':').replace('\\', '') for f in fields]
            if len(fields) >= 9:
                active = fields[0].strip()
                ssid = fields[1].strip()
                if not ssid:
                    ssid = "<hidden>"  # empty SSID
                bssid = fields[2].strip()
                signal_percent = int(fields[3]) if fields[3].isdigit() else 0
                channel = fields[4].strip()
                freq = fields[5].replace(" MHz","").strip()
                mode = fields[6].strip()
                rate = fields[7].strip()
                security = fields[8].strip()
                band = "2.4GHz" if freq and freq.startswith("2") else "5GHz"
                
                networks.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "rssi": -100,  # Will be overwritten by iwlist if available
                    "signal": signal_percent,
                    "channel": channel,
                    "freq": freq,
                    "band": band,
                    "mode": mode,
                    "rate": rate,
                    "security": security,
                    "active": (active == "yes"),
                })
                
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        # If nmcli fails, return empty list
        pass
        
    return networks
