# __main__.py
# ------------
# Entry point for TinyWiFi CLI when run with 'python -m tinywifi'.
# Imports and runs the main CLI logic from cli.py.
#
# Author: Jason A. Cox
# 17 July 2025
# github.com/jasonacox/tinywifi
from tinywifi import __version__, __author__
from .cli import main

print(f"TinyWiFi {__version__}")
print()


if __name__ == "__main__":
    main()
