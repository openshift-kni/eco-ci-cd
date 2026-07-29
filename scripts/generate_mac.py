#!/usr/bin/env python3
"""Generate a MAC address based on the current date and time."""

import sys
import time
import hashlib


VENDOR_PREFIXES = [
    (0xDA, 0xA1, 0x19),  # DA:A1:19
    (0x5E, 0xCF, 0x7F),  # 5E:CF:7F
]


def generate_mac(epoch_ms=None):
    if epoch_ms is None:
        epoch_ms = int(time.time() * 1000)

    prefix = VENDOR_PREFIXES[epoch_ms % len(VENDOR_PREFIXES)]

    digest = hashlib.sha256(str(epoch_ms).encode()).digest()
    suffix = list(digest[:3])

    return ":".join(f"{b:02x}" for b in list(prefix) + suffix)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        epoch_ms = int(sys.argv[1])
    else:
        epoch_ms = int(time.time() * 1000)

    print(f"Epoch ms:  {epoch_ms}")
    print(f"MAC:       {generate_mac(epoch_ms)}")
