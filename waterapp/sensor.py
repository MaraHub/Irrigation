"""
Environmental sensor interface for humidity and temperature readings.
"""
import logging
import requests
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SensorError(Exception):
    """Base exception for sensor-related errors."""
    pass


class SensorTimeoutError(SensorError):
    """Sensor did not respond within timeout period."""
    pass


class SensorDataError(SensorError):
    """Sensor returned invalid or incomplete data."""
    pass


class EnvironmentSensor:
    """
    Manages communication with the environmental sensor.
    Includes caching and retry logic for reliability.
    """
    
    def __init__(self, ip: str, timeout: float = 10.0, cache_duration: int = 60):
        """
        Initialize sensor interface.
        
        Args:
            ip: IP address of the sensor
            timeout: Request timeout in seconds
            cache_duration: How long to cache readings (seconds)
        """
        self.ip = ip
        self.timeout = timeout
        self.cache_duration = cache_duration
        
        # Cache variables
        self._cached_data: Optional[Dict] = None
        self._cache_time: Optional[datetime] = None
        
        # Error tracking
        self._consecutive_errors = 0
        self._last_error: Optional[str] = None
        
    def get_environment(self, use_cache: bool = True) -> Optional[Dict[str, float]]:
        """
        Get current temperature and humidity readings.
        
        Args:
            use_cache: If True, return cached data if available and fresh
            
        Returns:
            Dict with 'temp' and 'hum' keys, or None if unavailable
        """
        # Check cache first
        if use_cache and self._is_cache_valid():
            logger.debug(f"[SENSOR] Using cached data from {self._cache_time}")
            return self._cached_data
        
        # Fetch fresh data
        return self._fetch_fresh_data()
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._cached_data is None or self._cache_time is None:
            return False
        
        age = (datetime.now() - self._cache_time).total_seconds()
        return age < self.cache_duration
    
    def _fetch_fresh_data(self) -> Optional[Dict[str, float]]:
        """Fetch data directly from sensor."""
        url = f"http://{self.ip}"
        logger.info(f"[SENSOR] Querying {url}")
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"[SENSOR] Raw response: {data}")
            
            # Parse and validate data
            parsed = self._parse_sensor_data(data)
            
            if parsed is None:
                raise SensorDataError(f"Missing required fields in response: {data}")
            
            # Update cache
            self._cached_data = parsed
            self._cache_time = datetime.now()
            
            # Reset error counter on success
            self._consecutive_errors = 0
            self._last_error = None
            
            logger.info(f"[SENSOR] Success: temp={parsed['temp']:.1f}°C, hum={parsed['hum']:.1f}%")
            return parsed
            
        except requests.exceptions.Timeout:
            error_msg = f"Sensor timeout after {self.timeout}s"
            self._handle_error(error_msg)
            raise SensorTimeoutError(error_msg)
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to sensor at {self.ip}"
            self._handle_error(error_msg)
            logger.error(f"[SENSOR] {error_msg}: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error from sensor: {e.response.status_code}"
            self._handle_error(error_msg)
            logger.error(f"[SENSOR] {error_msg}")
            return None
            
        except ValueError as e:
            error_msg = f"Invalid JSON response from sensor"
            self._handle_error(error_msg)
            logger.error(f"[SENSOR] {error_msg}: {e}")
            return None
            
        except SensorDataError as e:
            self._handle_error(str(e))
            logger.error(f"[SENSOR] {e}")
            return None
            
        except Exception as e:
            error_msg = f"Unexpected error communicating with sensor"
            self._handle_error(error_msg)
            logger.exception(f"[SENSOR] {error_msg}: {e}")
            return None
    
    def _parse_sensor_data(self, data: dict) -> Optional[Dict[str, float]]:
        """
        Extract and validate temperature and humidity from sensor response.
        
        Supports multiple possible field names for compatibility.
        """
        # Try multiple possible key names
        temp = data.get("temp") or data.get("temperature")
        hum = data.get("hum") or data.get("humidity")
        
        if temp is None or hum is None:
            return None
        
        try:
            temp = float(temp)
            hum = float(hum)
            
            # Sanity checks
            if not (-50 <= temp <= 70):
                logger.warning(f"[SENSOR] Temperature {temp}°C outside expected range")
            
            if not (0 <= hum <= 100):
                logger.warning(f"[SENSOR] Humidity {hum}% outside valid range (0-100)")
                return None
            
            return {"temp": temp, "hum": hum}
            
        except (ValueError, TypeError) as e:
            logger.error(f"[SENSOR] Cannot convert to float: temp={temp}, hum={hum}, error={e}")
            return None
    
    def _handle_error(self, error_msg: str):
        """Track errors for monitoring."""
        self._consecutive_errors += 1
        self._last_error = error_msg
        logger.warning(f"[SENSOR] Error #{self._consecutive_errors}: {error_msg}")
    
    def get_status(self) -> Dict:
        """Get sensor health status for monitoring."""
        return {
            "ip": self.ip,
            "consecutive_errors": self._consecutive_errors,
            "last_error": self._last_error,
            "cache_valid": self._is_cache_valid(),
            "cached_data": self._cached_data,
            "cache_age_seconds": (
                (datetime.now() - self._cache_time).total_seconds()
                if self._cache_time else None
            )
        }
    
    def clear_cache(self):
        """Force cache refresh on next read."""
        self._cached_data = None
        self._cache_time = None
        logger.info("[SENSOR] Cache cleared")


# Legacy function for backward compatibility
def get_environment(ip: str, timeout: float = 10.0) -> Optional[Dict[str, float]]:
    """
    Legacy function - creates a one-time sensor instance.
    For better performance, use the EnvironmentSensor class directly.
    """
    sensor = EnvironmentSensor(ip, timeout, cache_duration=0)  # No caching
    return sensor.get_environment(use_cache=False)
