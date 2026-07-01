#!/usr/bin/env python3
"""
Custom Ansible filters for duration normalization.
Converts various duration formats to consistent XhYYmZZs format.
"""

import re


def duration_to_seconds(duration_str):
    """
    Convert duration string to total seconds.

    Supports formats:
    - "59.994" or "59.994s" -> 59 seconds
    - "5m" -> 300 seconds
    - "10m" -> 600 seconds
    - "1h" -> 3600 seconds
    - "2h30m" -> 9000 seconds
    - "1h13m11s" or "4391.0s" -> 4391 seconds
    - "18s" -> 18 seconds

    Args:
        duration_str: Duration string in various formats

    Returns:
        int: Total seconds
    """
    if not duration_str or duration_str == 'N/A':
        return 0

    duration_str = str(duration_str).strip()
    total_seconds = 0

    # Try to match "XhYYmZZs" or "XhYYm" or "XhZZs" or "YYmZZs" patterns
    # Pattern: optional hours, optional minutes, optional seconds
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s?)?'
    match = re.match(pattern, duration_str)

    if match and any(match.groups()):
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = float(match.group(3)) if match.group(3) else 0

        total_seconds = hours * 3600 + minutes * 60 + int(seconds)
    else:
        # Try to parse as plain number (assume seconds)
        try:
            total_seconds = int(float(duration_str))
        except ValueError:
            total_seconds = 0

    return total_seconds


def seconds_to_hms(seconds):
    """
    Convert seconds to XhYYmZZs format.

    Rules:
    - If hours > 0: show all (e.g., "1h13m11s", "2h00m00s")
    - If only minutes and seconds: show both (e.g., "5m00s", "0m18s")
    - If only seconds: show seconds (e.g., "0m18s")
    - Always show at least "0m00s" for zero duration

    Args:
        seconds: Total seconds (int or float)

    Returns:
        str: Duration in XhYYmZZs format
    """
    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m{secs:02d}s"
    else:
        return f"0m{secs:02d}s"


class FilterModule(object):
    """Ansible filter module for duration normalization."""

    def filters(self):
        return {
            'telco_kpis_duration_to_seconds': duration_to_seconds,
            'telco_kpis_seconds_to_hms': seconds_to_hms,
        }
