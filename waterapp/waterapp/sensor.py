# waterapp/sensor.py
import requests

def get_environment(ip: str, timeout: float = 10.0):
    """
    Call http://<ip> and expect JSON with keys like:
      {"datetime": "...", "humidity": 59.4, "temp": 21.4}

    Returns dict {"temp": float, "hum": float} or None on error.
    """
    print(f"[SENSOR] querying http://{ip}")
    try:
        r = requests.get(f"http://{ip}", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        print(f"[SENSOR] raw data: {data}")

        # Try multiple possible key names
        temp = data.get("temp") or data.get("temperature")
        hum  = data.get("hum") or data.get("humidity")

        if temp is None or hum is None:
            print(f"[SENSOR] missing keys in JSON: {data}")
            return None

        temp = float(temp)
        hum  = float(hum)

        print(f"[SENSOR] parsed temp={temp}, hum={hum}")
        return {"temp": temp, "hum": hum}

    except Exception as e:
        print(f"[SENSOR] error talking to sensor at {ip}: {e}")
        return None

