"""Constants for the AAT Multiroom integration."""
from __future__ import annotations

DOMAIN = "aat_multiroom"

# Config entry / config flow keys
CONF_NUM_ZONES = "num_zones"
CONF_ZONE_NAMES = "zone_names"
CONF_SOURCES = "sources"  # mapping of input number -> friendly name

# Defaults
DEFAULT_PORT = 5000
DEFAULT_NUM_ZONES = 4
DEFAULT_SCAN_INTERVAL = 30  # seconds between background polls

# Volume scaling: AAT goes 0..87, HA media_player expects 0.0..1.0.
AAT_VOLUME_MAX = 87

# Number of inputs per model (API spec Rev.10, page 1).
# Used by the config flow to show the correct number of source name fields.
MODEL_INPUTS: dict[str, int] = {
    "PMR4": 4,
    "PMR5": 4,
    "PMR6": 6,
    "PMR7": 6,
    "PMR8": 5,
}
MAX_NUM_INPUTS = 8  # platform maximum across all models
