# Shelly Connection Troubleshooting

## Your Current Error

```
[SHELLY] Cannot connect to Shelly at 10.42.0.56
[SHELLY] Failed to turn ON device S2
```

This means the Shelly device at IP `10.42.0.56` (S2 - Bostani) is not responding.

## Quick Diagnostic Steps

### 1. Run the Test Script

```bash
cd ~/irrigation
source venv/bin/activate
python3 test_shelly.py
```

This will test both Shelly devices and show exactly what's wrong.

### 2. Check Network Connectivity

```bash
# Ping the Shelly
ping 10.42.0.56

# If it doesn't respond:
# - Device is powered off
# - Wrong IP address
# - Network issue
```

### 3. Check IP Address

Shelly IPs can change if not set to static. Check in your router:

1. Find device with MAC address shown in Shelly app
2. Set DHCP reservation to keep IP stable
3. Update `waterapp/config.py` if IP changed

### 4. Test Manually with curl

```bash
# Get device info
curl "http://10.42.0.56/rpc/Shelly.GetDeviceInfo"

# Turn ON
curl "http://10.42.0.56/rpc/Switch.Set?id=0&on=true"

# Turn OFF
curl "http://10.42.0.56/rpc/Switch.Set?id=0&on=false"

# Get status
curl "http://10.42.0.56/rpc/Switch.GetStatus?id=0"
```

### 5. Check Shelly Web Interface

Open in browser:
```
http://10.42.0.56
```

If this doesn't load, the device is not accessible.

## Common Issues & Solutions

### Issue 1: IP Address Changed
**Symptom**: Used to work, now doesn't
**Solution**: 
1. Open Shelly app on phone
2. Find the device
3. Note the new IP address
4. Update `waterapp/config.py`:
   ```python
   SHELLY_ZONES = {
       "S2": {
           "ip": "10.42.0.XX",  # New IP here
           ...
       }
   }
   ```
5. Restart application: `sudo systemctl restart irrigation`

### Issue 2: Shelly Offline
**Symptom**: Cannot ping, web interface doesn't load
**Solution**:
1. Check power cable
2. Check Wi-Fi connection in Shelly app
3. Reboot Shelly (power cycle)
4. Check router shows device as connected

### Issue 3: Wrong Switch ID
**Symptom**: Commands fail or control wrong output
**Solution**:
- For Shelly Plus 1: `rpc_id` should be `0`
- For Shelly Plus 2PM: `rpc_id` can be `0` or `1` (two outputs)
- Check in config.py

### Issue 4: Firmware Too Old
**Symptom**: RPC commands not recognized
**Solution**:
1. Update Shelly firmware via web interface
2. Minimum version: 1.0.0 for Plus series

### Issue 5: Network Timeout
**Symptom**: Intermittent failures, slow response
**Solution**:
1. Check Wi-Fi signal strength at Shelly location
2. Increase timeout in `config.py`:
   ```python
   SHELLY_ZONES = {
       "S2": {
           "timeout": 10.0,  # Increase from 5.0
       }
   }
   ```

## Verify Configuration

Your current config should look like:

```python
SHELLY_ZONES = {
    "S1": {
        "ip": "10.42.0.82",
        "rpc_id": 0,
        "name": "New Gazon",
        "timeout": 5.0,
    },
    "S2": {
        "ip": "10.42.0.56",  # ← Check this IP is correct!
        "rpc_id": 0,
        "name": "Bostani",
        "timeout": 5.0,
    }
}
```

## How the System Handles Failures

The improved system:
1. ✓ Logs the error (you see it in logs)
2. ✓ Shows warning in UI
3. ✓ Marks device as failed after 3 consecutive errors
4. ✓ Waits 5 minutes before retrying
5. ✓ Other zones continue working
6. ✓ Automatically recovers when device comes back

## Real-Time Monitoring

### View Status
```bash
# Check if device is marked as failed
curl http://localhost:8080/api/status | python3 -m json.tool

# Check recent errors
curl http://localhost:8080/api/hardware_errors | python3 -m json.tool
```

### Watch Logs
```bash
# Live log watching
tail -f ~/irrigation/waterapp.log

# Or systemd logs
sudo journalctl -u irrigation.service -f
```

## Emergency Actions

### Option 1: Disable Failed Shelly Temporarily
Edit `waterapp/config.py` and comment out the problematic device:

```python
SHELLY_ZONES = {
    "S1": {
        "ip": "10.42.0.82",
        "rpc_id": 0,
        "name": "New Gazon",
    },
    # "S2": {  # Temporarily disabled
    #     "ip": "10.42.0.56",
    #     "rpc_id": 0,
    #     "name": "Bostani",
    # }
}
```

Then restart: `sudo systemctl restart irrigation`

### Option 2: Use Only GPIO Relays
If Shelly is unreliable, you can remove it and use only GPIO relays.

## Getting More Help

If issue persists:

1. Run diagnostic: `python3 test_shelly.py > shelly_test.txt`
2. Check full logs: `tail -100 ~/irrigation/waterapp.log > app_log.txt`
3. Check hardware errors: `cat ~/irrigation/waterapp/hardware_errors.json > hw_errors.txt`
4. Share these three files for analysis

## Prevention

To avoid future issues:

1. **Set Static IP**: Configure DHCP reservation in router
2. **Use Cable**: Ethernet is more reliable than Wi-Fi
3. **Check Signal**: Ensure good Wi-Fi coverage
4. **Update Firmware**: Keep Shelly firmware current
5. **Monitor**: Check `/api/status` regularly
