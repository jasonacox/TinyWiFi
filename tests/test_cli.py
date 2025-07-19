import subprocess
import sys
import re

def test_cli_scan(monkeypatch):
    # Patch subprocess.run to return a fake system_profiler output
    class FakeCompletedProcess:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0
    sample_output = '''
        Other Local Wi-Fi Networks:
            MyHomeWiFi:
                PHY Mode: 802.11ax
                Channel: 6 (2GHz, 20MHz)
                Network Type: Infrastructure
                Security: WPA2 Personal
                Signal / Noise: -48 dBm / -94 dBm
            Office5G:
                PHY Mode: 802.11ac
                Channel: 149 (5GHz, 80MHz)
                Network Type: Infrastructure
                Security: WPA2 Personal
                Signal / Noise: -60 dBm / -92 dBm
    '''
    def fake_run(*args, **kwargs):
        return FakeCompletedProcess(sample_output)
    monkeypatch.setattr('subprocess.run', fake_run)

    # Run the CLI as a module
    from tinywifi.cli import main
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    sys.argv = ['tinywifi', 'scan']
    with redirect_stdout(f):
        main()
    output = f.getvalue()
    # Check for expected SSIDs and colored output
    assert 'MyHomeWiFi' in output
    assert 'Office5G' in output
    assert re.search(r'2\.4GHz', output)
    assert re.search(r'5GHz', output)
    assert 'Scanning for WiFi networks' in output
