"""
Hardware abstraction layer for GPIO relays and Shelly devices.
Provides error handling, retry logic, and fallback mechanisms.
"""
import logging
import time
import requests
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from .config import (
    RELAYS, SHELLY_ZONES, ACTIVE_LOW, USE_MOCK_HARDWARE,
    MAX_CONSECUTIVE_ERRORS, HARDWARE_RETRY_COOLDOWN
)

logger = logging.getLogger(__name__)


# ============================================================================
# Hardware Errors
# ============================================================================

class HardwareError(Exception):
    """Base exception for hardware-related errors."""
    pass


class GPIOError(HardwareError):
    """GPIO-related errors."""
    pass


class ShellyError(HardwareError):
    """Shelly device errors."""
    pass


# ============================================================================
# Hardware Status Tracking
# ============================================================================

class HardwareStatus:
    """Track health status of individual hardware devices."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.consecutive_errors = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.is_failed = False
        
    def record_success(self):
        """Record successful operation."""
        self.consecutive_errors = 0
        self.last_success_time = datetime.now()
        self.is_failed = False
        
    def record_error(self, error_msg: str):
        """Record failed operation."""
        self.consecutive_errors += 1
        self.last_error = error_msg
        self.last_error_time = datetime.now()
        
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            self.is_failed = True
            logger.error(
                f"[HARDWARE] Device {self.device_id} marked as FAILED after "
                f"{self.consecutive_errors} consecutive errors"
            )
    
    def can_retry(self) -> bool:
        """Check if enough time has passed to retry failed hardware."""
        if not self.is_failed:
            return True
        
        if self.last_error_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_error_time).total_seconds()
        return elapsed >= HARDWARE_RETRY_COOLDOWN
    
    def get_status_dict(self) -> Dict:
        """Get status as dictionary for API responses."""
        return {
            "device_id": self.device_id,
            "is_failed": self.is_failed,
            "consecutive_errors": self.consecutive_errors,
            "last_error": self.last_error,
            "last_error_time": (
                self.last_error_time.isoformat() if self.last_error_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "can_retry": self.can_retry()
        }


# Global hardware status tracker
_hardware_status: Dict[str, HardwareStatus] = {}


def get_hardware_status(device_id: str) -> HardwareStatus:
    """Get or create hardware status tracker."""
    if device_id not in _hardware_status:
        _hardware_status[device_id] = HardwareStatus(device_id)
    return _hardware_status[device_id]


def get_all_hardware_status() -> Dict[str, Dict]:
    """Get status of all hardware devices."""
    return {
        device_id: status.get_status_dict()
        for device_id, status in _hardware_status.items()
    }


# ============================================================================
# Mock Hardware (for testing)
# ============================================================================

class MockDevice:
    """Mock hardware device for testing without physical hardware."""
    
    def __init__(self, name: str):
        self.name = name
        self._state = False
        logger.info(f"[MOCK] Created mock device: {name}")
    
    def on(self):
        """Turn device on."""
        self._state = True
        logger.info(f"[MOCK] {self.name} → ON")
        
    def off(self):
        """Turn device off."""
        self._state = False
        logger.info(f"[MOCK] {self.name} → OFF")
    
    def is_on(self) -> bool:
        """Check if device is on."""
        return self._state


# ============================================================================
# GPIO Relay Control
# ============================================================================

class GPIORelay:
    """Controls a single GPIO relay with error handling."""
    
    def __init__(self, pin: int, relay_id: str, active_low: bool = True):
        """
        Initialize GPIO relay.
        
        Args:
            pin: GPIO pin number (BCM mode)
            relay_id: Unique identifier for this relay
            active_low: If True, relay activates on LOW signal
        """
        self.pin = pin
        self.relay_id = relay_id
        self.active_low = active_low
        self.status = get_hardware_status(relay_id)
        
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            
            # Setup GPIO
            self.GPIO.setmode(GPIO.BCM)
            self.GPIO.setwarnings(False)
            self.GPIO.setup(self.pin, GPIO.OUT)
            
            # Initialize to OFF state
            self.off()
            
            self.status.record_success()
            logger.info(f"[GPIO] Initialized relay {relay_id} on pin {pin}")
            
        except ImportError:
            raise GPIOError("RPi.GPIO library not available")
        except Exception as e:
            error_msg = f"Failed to initialize GPIO pin {pin}"
            self.status.record_error(error_msg)
            logger.error(f"[GPIO] {error_msg}: {e}")
            raise GPIOError(error_msg) from e
    
    def on(self):
        """Turn relay ON."""
        if not self.status.can_retry():
            logger.warning(f"[GPIO] Relay {self.relay_id} in cooldown, skipping ON command")
            return
        
        try:
            state = self.GPIO.LOW if self.active_low else self.GPIO.HIGH
            self.GPIO.output(self.pin, state)
            self.status.record_success()
            logger.info(f"[GPIO] Relay {self.relay_id} (pin {self.pin}) → ON")
            
        except Exception as e:
            error_msg = f"Failed to turn ON relay {self.relay_id}"
            self.status.record_error(error_msg)
            logger.error(f"[GPIO] {error_msg}: {e}")
            raise GPIOError(error_msg) from e
    
    def off(self):
        """Turn relay OFF."""
        if not self.status.can_retry():
            logger.warning(f"[GPIO] Relay {self.relay_id} in cooldown, skipping OFF command")
            return
        
        try:
            state = self.GPIO.HIGH if self.active_low else self.GPIO.LOW
            self.GPIO.output(self.pin, state)
            self.status.record_success()
            logger.info(f"[GPIO] Relay {self.relay_id} (pin {self.pin}) → OFF")
            
        except Exception as e:
            error_msg = f"Failed to turn OFF relay {self.relay_id}"
            self.status.record_error(error_msg)
            logger.error(f"[GPIO] {error_msg}: {e}")
            raise GPIOError(error_msg) from e


# ============================================================================
# Shelly Device Control
# ============================================================================

class ShellyDevice:
    """Controls a Shelly smart switch via HTTP API."""
    
    def __init__(self, device_id: str, ip: str, rpc_id: int = 0, timeout: float = 5.0):
        """
        Initialize Shelly device.
        
        Args:
            device_id: Unique identifier
            ip: IP address of the Shelly device
            rpc_id: RPC endpoint ID (usually 0)
            timeout: Request timeout in seconds
        """
        self.device_id = device_id
        self.ip = ip
        self.rpc_id = rpc_id
        self.timeout = timeout
        self.status = get_hardware_status(device_id)
        
        logger.info(f"[SHELLY] Initialized device {device_id} at {ip}")
    
    def _send_command(self, method: str, params: Optional[Dict] = None) -> bool:
        """
        Send RPC command to Shelly device.
        
        Returns True on success, False on failure.
        """
        if not self.status.can_retry():
            logger.warning(f"[SHELLY] Device {self.device_id} in cooldown, skipping command")
            return False
        
        url = f"http://{self.ip}/rpc"
        payload = {
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        try:
            logger.debug(f"[SHELLY] Sending to {url}: {payload}")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"[SHELLY] Response: {data}")
            
            if "error" in data:
                raise ShellyError(f"Shelly returned error: {data['error']}")
            
            self.status.record_success()
            return True
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout connecting to Shelly at {self.ip}"
            self.status.record_error(error_msg)
            logger.error(f"[SHELLY] {error_msg}")
            return False
            
        except requests.exceptions.ConnectionError:
            error_msg = f"Cannot connect to Shelly at {self.ip}"
            self.status.record_error(error_msg)
            logger.error(f"[SHELLY] {error_msg}")
            return False
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error from Shelly: {e.response.status_code}"
            self.status.record_error(error_msg)
            logger.error(f"[SHELLY] {error_msg}")
            return False
            
        except Exception as e:
            error_msg = f"Unexpected error communicating with Shelly"
            self.status.record_error(error_msg)
            logger.exception(f"[SHELLY] {error_msg}: {e}")
            return False
    
    def on(self):
        """Turn Shelly switch ON."""
        success = self._send_command(
            "Switch.Set",
            {"id": self.rpc_id, "on": True}
        )
        if success:
            logger.info(f"[SHELLY] Device {self.device_id} → ON")
        else:
            logger.error(f"[SHELLY] Failed to turn ON device {self.device_id}")
    
    def off(self):
        """Turn Shelly switch OFF."""
        success = self._send_command(
            "Switch.Set",
            {"id": self.rpc_id, "on": False}
        )
        if success:
            logger.info(f"[SHELLY] Device {self.device_id} → OFF")
        else:
            logger.error(f"[SHELLY] Failed to turn OFF device {self.device_id}")


# ============================================================================
# Hardware Manager
# ============================================================================

_hardware_cache: Optional[Dict[str, Any]] = None


def init_hardware() -> Dict[str, Any]:
    """
    Initialize all hardware devices (GPIO relays and Shelly switches).
    
    Returns a dictionary mapping zone IDs to device objects.
    Caches initialized devices for reuse.
    """
    global _hardware_cache
    
    if _hardware_cache is not None:
        return _hardware_cache
    
    logger.info("=" * 60)
    logger.info("[HARDWARE] Initializing all devices...")
    logger.info(f"[HARDWARE] Mock mode: {USE_MOCK_HARDWARE}")
    
    devices = {}
    errors = []
    
    # Initialize GPIO relays
    if USE_MOCK_HARDWARE:
        logger.info("[HARDWARE] Using MOCK GPIO relays")
        for relay_id, pin in RELAYS.items():
            devices[relay_id] = MockDevice(f"GPIO-{relay_id}")
    else:
        logger.info("[HARDWARE] Initializing REAL GPIO relays")
        for relay_id, pin in RELAYS.items():
            try:
                devices[relay_id] = GPIORelay(pin, relay_id, ACTIVE_LOW)
            except Exception as e:
                error_msg = f"Failed to initialize GPIO relay {relay_id}: {e}"
                errors.append(error_msg)
                logger.error(f"[HARDWARE] {error_msg}")
                # Create mock device as fallback
                devices[relay_id] = MockDevice(f"GPIO-{relay_id}-FAILED")
    
    # Initialize Shelly devices
    logger.info("[HARDWARE] Initializing Shelly devices")
    for zone_id, config in SHELLY_ZONES.items():
        try:
            if USE_MOCK_HARDWARE:
                devices[zone_id] = MockDevice(f"Shelly-{zone_id}")
            else:
                devices[zone_id] = ShellyDevice(
                    zone_id,
                    config["ip"],
                    config["rpc_id"],
                    config.get("timeout", 5.0)
                )
        except Exception as e:
            error_msg = f"Failed to initialize Shelly {zone_id}: {e}"
            errors.append(error_msg)
            logger.error(f"[HARDWARE] {error_msg}")
            # Create mock device as fallback
            devices[zone_id] = MockDevice(f"Shelly-{zone_id}-FAILED")
    
    _hardware_cache = devices
    
    logger.info(f"[HARDWARE] Initialized {len(devices)} devices")
    if errors:
        logger.warning(f"[HARDWARE] Encountered {len(errors)} errors during initialization")
        for err in errors:
            logger.warning(f"  - {err}")
    logger.info("=" * 60)
    
    return devices


def all_off():
    """Turn off all zones immediately."""
    logger.info("[HARDWARE] Turning OFF all zones")
    devices = init_hardware()
    errors = []
    
    for zone_id, device in devices.items():
        try:
            device.off()
        except Exception as e:
            error_msg = f"Error turning off {zone_id}"
            errors.append(error_msg)
            logger.error(f"[HARDWARE] {error_msg}: {e}")
    
    if errors:
        logger.warning(f"[HARDWARE] {len(errors)} zones failed to turn off")
    else:
        logger.info("[HARDWARE] All zones turned OFF successfully")


def exclusive_on(zone_id: str):
    """
    Turn on a specific zone and ensure all others are off.
    
    Args:
        zone_id: The zone to activate (e.g., 'R1', 'S1')
    """
    logger.info(f"[HARDWARE] Exclusive activation: {zone_id}")
    devices = init_hardware()
    
    if zone_id not in devices:
        logger.error(f"[HARDWARE] Unknown zone ID: {zone_id}")
        raise ValueError(f"Unknown zone: {zone_id}")
    
    errors = []
    
    # Turn off all zones first
    for zid, device in devices.items():
        if zid != zone_id:
            try:
                device.off()
            except Exception as e:
                errors.append(f"Failed to turn off {zid}: {e}")
    
    # Turn on target zone
    try:
        devices[zone_id].on()
    except Exception as e:
        error_msg = f"Failed to turn on {zone_id}: {e}"
        errors.append(error_msg)
        logger.error(f"[HARDWARE] {error_msg}")
        raise HardwareError(error_msg) from e
    
    if errors:
        logger.warning(f"[HARDWARE] Errors during exclusive_on:")
        for err in errors:
            logger.warning(f"  - {err}")


def cleanup_hardware():
    """Clean up hardware resources (call on shutdown)."""
    logger.info("[HARDWARE] Cleaning up...")
    
    try:
        all_off()
    except Exception as e:
        logger.error(f"[HARDWARE] Error during cleanup: {e}")
    
    # Clear cache
    global _hardware_cache
    _hardware_cache = None
    
    # GPIO cleanup (if using real hardware)
    if not USE_MOCK_HARDWARE:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            logger.info("[HARDWARE] GPIO cleanup complete")
        except Exception as e:
            logger.error(f"[HARDWARE] GPIO cleanup error: {e}")
