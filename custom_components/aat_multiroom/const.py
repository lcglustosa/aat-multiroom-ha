"""Constants for the AAT Multiroom integration."""
from __future__ import annotations

DOMAIN = "aat_multiroom"

# Config entry / config flow keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_NUM_ZONES = "num_zones"
CONF_ZONE_NAMES = "zone_names"
CONF_SOURCES = "sources"  # mapping of input number -> friendly name

# Defaults
DEFAULT_PORT = 5000
DEFAULT_NUM_ZONES = 4
DEFAULT_SCAN_INTERVAL = 30  # seconds between background polls

# Volume scaling: AAT goes 0..87, HA media_player expects 0.0..1.0.
AAT_VOLUME_MAX = 87
