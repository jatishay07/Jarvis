#!/usr/bin/env python3
"""List input devices and default — use index or name substring in jarvis.json clap.input_device."""
import sys

try:
    import sounddevice as sd
except ImportError:
    print("pip install sounddevice", file=sys.stderr)
    sys.exit(1)

print("Input-capable devices (use the index in clap.input_device):\n")
for i, d in enumerate(sd.query_devices()):
    ch = int(d.get("max_input_channels", 0))
    if ch < 1:
        continue
    print(f"  {i}: {d['name']}")
def_in, def_out = sd.default.device
print(f"\nDefault input index: {def_in}")
