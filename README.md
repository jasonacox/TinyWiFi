# TinyWiFi

Simple, modern Python command line WiFi signal analysis tool.

## Features

- Scan for WiFi SSIDs, reporting signal, frequency, channel, and band (2.4GHz/5GHz)
- Easy-to-read, full-color table outputs
- Cross-platform: macOS, Linux (nmcli), Raspberry Pi, Windows (planned)
- Monitor SSID details live
- Modern packaging with `pyproject.toml`

## Quick Start

```bash
# Install from source (recommended for latest features)
git clone https://github.com/jasonacox/tinywifi.git
cd tinywifi
pip install .

# Or install from PyPI (when available)
pip install tinywifi

# Scan and print table
tinywifi scan

# Monitor SSID details
tinywifi monitor "MyWiFi"
```

## Example Output

```
SSID                             Signal   Freq     Channel  Band    State   
MyHomeWiFi                       -48      2437     6        2.4GHz         
Office5G                         -60      5745     149      5GHz           
*TheOuthouse                     -36      2437     6        2.4GHz  Connected
```

## Contributions

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on GitHub.

## License

MIT

## References

