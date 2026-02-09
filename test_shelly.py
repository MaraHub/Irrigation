#!/usr/bin/env python3
"""
Diagnostic script to test Shelly device connectivity.
Run this to troubleshoot Shelly connection issues.
"""
import sys
import requests
import json

def test_shelly(ip, rpc_id=0):
    """Test connection to a Shelly device."""
    print(f"\n{'='*60}")
    print(f"Testing Shelly at {ip}")
    print(f"{'='*60}\n")
    
    # Test 1: Ping (basic connectivity)
    print(f"1. Testing basic connectivity...")
    try:
        response = requests.get(f"http://{ip}", timeout=3)
        print(f"   ✓ Device is reachable (status code: {response.status_code})")
    except requests.exceptions.Timeout:
        print(f"   ✗ TIMEOUT - Device did not respond within 3 seconds")
        print(f"   → Check if device is powered on")
        print(f"   → Verify IP address is correct")
        return False
    except requests.exceptions.ConnectionError:
        print(f"   ✗ CONNECTION ERROR - Cannot reach device")
        print(f"   → Check network connection")
        print(f"   → Verify device is on same network")
        print(f"   → Try: ping {ip}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 2: Get device info
    print(f"\n2. Getting device info...")
    try:
        response = requests.get(f"http://{ip}/rpc/Shelly.GetDeviceInfo", timeout=3)
        if response.status_code == 200:
            info = response.json()
            print(f"   ✓ Device info retrieved:")
            print(f"     Model: {info.get('model', 'Unknown')}")
            print(f"     Firmware: {info.get('fw_id', 'Unknown')}")
            print(f"     MAC: {info.get('mac', 'Unknown')}")
        else:
            print(f"   ! Status code: {response.status_code}")
    except Exception as e:
        print(f"   ! Could not get device info: {e}")
    
    # Test 3: Get switch status
    print(f"\n3. Getting switch status...")
    try:
        response = requests.get(
            f"http://{ip}/rpc/Switch.GetStatus",
            params={"id": rpc_id},
            timeout=3
        )
        if response.status_code == 200:
            status = response.json()
            print(f"   ✓ Switch status retrieved:")
            print(f"     Switch {rpc_id} is: {'ON' if status.get('output') else 'OFF'}")
            print(f"     Power: {status.get('apower', 0)} W")
        else:
            print(f"   ! Status code: {response.status_code}")
    except Exception as e:
        print(f"   ! Could not get switch status: {e}")
    
    # Test 4: Turn ON (actual test like your app does)
    print(f"\n4. Testing switch control (Turn ON)...")
    try:
        response = requests.get(
            f"http://{ip}/rpc/Switch.Set",
            params={"id": rpc_id, "on": "true"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"   ✓ Successfully sent ON command")
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
        else:
            print(f"   ✗ Failed with status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ Error sending ON command: {e}")
        return False
    
    # Test 5: Turn OFF
    print(f"\n5. Testing switch control (Turn OFF)...")
    try:
        response = requests.get(
            f"http://{ip}/rpc/Switch.Set",
            params={"id": rpc_id, "on": "false"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"   ✓ Successfully sent OFF command")
            result = response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
        else:
            print(f"   ✗ Failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error sending OFF command: {e}")
        return False
    
    print(f"\n{'='*60}")
    print(f"✓ All tests passed! Shelly at {ip} is working correctly.")
    print(f"{'='*60}\n")
    return True


if __name__ == "__main__":
    # Test your Shelly devices
    print("Shelly Device Diagnostic Tool")
    print("=" * 60)
    
    # From your config
    shellies = [
        {"ip": "10.42.0.82", "rpc_id": 0, "name": "S1 - New Gazon"},
        {"ip": "10.42.0.56", "rpc_id": 0, "name": "S2 - Bostani"},
    ]
    
    results = []
    for shelly in shellies:
        success = test_shelly(shelly["ip"], shelly["rpc_id"])
        results.append((shelly["name"], success))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "✓ OK" if success else "✗ FAILED"
        print(f"{status:12} {name}")
    print("=" * 60)
    
    # Exit code
    sys.exit(0 if all(r[1] for r in results) else 1)
