"""
Configuration settings for the irrigation control system.
"""
import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Hardware Configuration
# ============================================================================

# Relay control mode (True = relay activates on LOW signal)
ACTIVE_LOW = True

# GPIO Relay mapping (Raspberry Pi GPIO BCM pins)
RELAYS = {
    "R1": 26,  # Veranda 1
    "R2": 20,  # Veranda 2
    "R3": 21,  # Veranda 3
}

# Zone display names (Greek labels)
NAMES = {
    "R1": "Βεράντα 1",
    "R2": "Βεράντα 2",
    "R3": "Βεράντα 3",
}

# ============================================================================
# Shelly Wi-Fi Zone Configuration
# ============================================================================

SHELLY_ZONES = {
    "S1": {
        "ip": "10.42.0.82",
        "rpc_id": 0,
        "name": "New Gazon",
        "timeout": 5.0,  # seconds
    },
    "S2": {
        "ip": "10.42.0.56",
        "rpc_id": 0,
        "name": "Bostani",
        "timeout": 5.0,
    }
}

# ============================================================================
# File Storage Paths
# ============================================================================

# Determine base directory based on user
if os.path.exists("/home/ic/irrigation"):
    BASE_DIR = "/home/ic/irrigation/waterapp"
else:
    # Fallback for development
    BASE_DIR = os.path.expanduser("~/Projects/IoT/Irrigation/waterapp/waterapp")

# Ensure directory exists
os.makedirs(BASE_DIR, exist_ok=True)

# Schedule storage file
SCHED_FILE = os.path.join(BASE_DIR, "schedules.json")

# Skip log file (stores humidity-based skips)
SKIP_LOG_FILE = os.path.join(BASE_DIR, "skipped_runs.json")

# Hardware error log
HARDWARE_ERROR_LOG = os.path.join(BASE_DIR, "hardware_errors.json")

# ============================================================================
# Scheduler Configuration
# ============================================================================

# How often to check for scheduled runs (seconds)
CHECK_INTERVAL_SEC = 10

# ============================================================================
# Sensor Configuration
# ============================================================================

# Humidity sensor IP address
SENSOR_IP = "10.42.0.27"

# If humidity is above this threshold, skip scheduled irrigation
HUMIDITY_SKIP_THRESHOLD = 95.0

# Sensor request timeout (seconds)
SENSOR_TIMEOUT = 10.0

# ============================================================================
# Mock Hardware Mode (for testing without physical hardware)
# ============================================================================

# Set environment variable WATERAPP_MOCK_HARDWARE=0 to use real hardware
USE_MOCK_HARDWARE = os.environ.get("WATERAPP_MOCK_HARDWARE", "1") == "1"

# ============================================================================
# Merge Zone Names and Create Ordering
# ============================================================================

# Add Shelly zone names to the main NAMES dict
NAMES.update({z_id: z_cfg["name"] for z_id, z_cfg in SHELLY_ZONES.items()})

# Default zone order (for schedules UI)
ZORDER = list(RELAYS.keys()) + list(SHELLY_ZONES.keys())

# ============================================================================
# Error Handling Configuration
# ============================================================================

# Maximum consecutive errors before marking hardware as failed
MAX_CONSECUTIVE_ERRORS = 3

# Cooldown period before retrying failed hardware (seconds)
HARDWARE_RETRY_COOLDOWN = 300  # 5 minutes

# ============================================================================
# Logging
# ============================================================================

logger.info("=" * 60)
logger.info("Configuration loaded from: %s", __file__)
logger.info("Base directory: %s", BASE_DIR)
logger.info("Schedule file: %s", SCHED_FILE)
logger.info("Mock hardware mode: %s", USE_MOCK_HARDWARE)
logger.info("GPIO Relays: %s", RELAYS)
logger.info("Shelly Zones: %s", list(SHELLY_ZONES.keys()))
logger.info("=" * 60)
