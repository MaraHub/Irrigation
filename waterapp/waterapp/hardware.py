# waterapp/hardware.py
import time
import requests

from .config import ACTIVE_LOW, RELAYS, SHELLY_ZONES, USE_MOCK_HARDWARE

try:
    from gpiozero import OutputDevice as RealOutputDevice
except ImportError:
    RealOutputDevice = None


# Mock implementations (for development without hardware)

class MockOutputDevice:
    def __init__(self, pin, active_high=True, initial_value=False):
        self.pin = pin
        self.active_high = active_high
        self._value = 1.0 if initial_value else 0.0
        print(f"[MOCK-GPIO] init pin={pin} active_high={active_high} initial={initial_value}")

    def on(self):
        self._value = 1.0
        print(f"[MOCK-GPIO] pin={self.pin} -> ON")

    def off(self):
        self._value = 0.0
        print(f"[MOCK-GPIO] pin={self.pin} -> OFF")

    @property
    def value(self):
        return self._value


class MockShellySwitch:
    def __init__(self, ip: str, rpc_id: int = 0, timeout: float = 3.0):
        self.ip = ip
        self.rpc_id = rpc_id
        self.timeout = timeout
        self._is_on = False
        print(f"[MOCK-SHELLY] init ip={ip} id={rpc_id}")

    def on(self):
        self._is_on = True
        print(f"[MOCK-SHELLY] ip={self.ip} id={self.rpc_id} -> ON")

    def off(self):
        self._is_on = False
        print(f"[MOCK-SHELLY] ip={self.ip} id={self.rpc_id} -> OFF")

    @property
    def value(self):
        return 1.0 if self._is_on else 0.0



# Real Shelly implementation (only used if not mocking)

class RealShellySwitch:
    def __init__(self, ip: str, rpc_id: int = 0, timeout: float = 3.0):
        self.ip = ip
        self.rpc_id = rpc_id
        self.timeout = timeout
        self._is_on = False

    def _rpc(self, on: bool):
        url = f"http://{self.ip}/rpc/Switch.Set"
        params = {"id": self.rpc_id, "on": "true" if on else "false"}
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        self._is_on = on

    def on(self):
        self._rpc(True)

    def off(self):
        self._rpc(False)

    @property
    def value(self):
        return 1.0 if self._is_on else 0.0


# Select implementation based on USE_MOCK_HARDWARE flag

if USE_MOCK_HARDWARE or RealOutputDevice is None:
    print("[HARDWARE] Using MOCK hardware")
    OutputDevice = MockOutputDevice
    ShellyClass = MockShellySwitch
else:
    print("[HARDWARE] Using REAL hardware")
    OutputDevice = RealOutputDevice
    ShellyClass = RealShellySwitch



# Devices dictionary (relays + Shelly zones)

_devices = None

def init_hardware():
    global _devices
    if _devices is not None:
        return _devices

    devs = {
        k: OutputDevice(pin, active_high=not ACTIVE_LOW, initial_value=False)
        for k, pin in RELAYS.items()
    }

    devs.update({
        z_id: ShellyClass(ip=cfg["ip"], rpc_id=cfg.get("rpc_id", 0))
        for z_id, cfg in SHELLY_ZONES.items()
    })

    _devices = devs
    return _devices




# Helper functions used by the rest of the app

def all_off():
    for k, d in init_hardware().items():
        try:
            d.off()
        except Exception as e:
            print(f"[HARDWARE] all_off error on {k}: {e}")

def exclusive_on(key: str):
    devs = init_hardware()
    for k, dev in devs.items():
        if k != key:
            try:
                dev.off()
            except Exception as e:
                print(f"[HARDWARE] exclusive_on off error on {k}: {e}")
    devs[key].on()
   
