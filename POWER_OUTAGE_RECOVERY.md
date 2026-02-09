# Power Outage Recovery Guide

## 🔌 What Happens During a Power Outage

When power is lost and restored:

1. **Raspberry Pi** - Reboots automatically (if auto-start is configured)
2. **Shelly Devices** - Reboot and reconnect to Wi-Fi automatically
3. **GPIO Relays** - Reset to OFF state (safe default)
4. **Schedules** - Resume normal operation once system is back online

## ✅ **NEW**: Last Connected Tracking

The improved system now tracks:
- ✅ **Last successful communication** with each device
- ✅ **Time since last contact** ("5m ago", "2h ago", etc.)
- ✅ **Last error message** for troubleshooting
- ✅ **Visual warnings** in UI when devices are offline

### What You'll See After Power Outage

When power returns, the UI will show:

```
⚠️ Προειδοποίηση Υλικού
Οι παρακάτω ζώνες δεν ανταποκρίνονται:

• Bostani (S2)
  Τελευταία επικοινωνία: 2h ago
  Σφάλμα: Cannot connect to Shelly at 10.42.0.56

• Βεράντα 2 (R2)
  Τελευταία επικοινωνία: Never
```

This tells you:
- Which devices were working before outage
- How long it's been since they responded
- What error occurred when trying to reconnect

## 🚀 Automatic Recovery

### Raspberry Pi
If you've set up the systemd service (recommended):

```bash
sudo systemctl enable irrigation.service
```

Then:
1. ✅ Power returns
2. ✅ Pi boots up
3. ✅ Irrigation service starts automatically
4. ✅ Schedules resume normal operation

### Shelly Devices
Shellies automatically:
1. ✅ Power on when electricity returns
2. ✅ Reconnect to Wi-Fi (usually 10-30 seconds)
3. ✅ Become available at their IP address
4. ✅ System detects them and shows "last seen" updated

### Recovery Timeline

```
T+0s    Power returns
T+30s   Raspberry Pi boots
T+45s   Irrigation service starts
T+60s   GPIO relays initialized
T+90s   Shelly devices reconnect to Wi-Fi
T+120s  System fully operational
```

## 📊 Monitoring Recovery

### Check System Status

Visit the web interface at:
```
http://<raspberry-pi-ip>:8080
```

You'll see:

1. **Green Success Messages** - Devices working normally
2. **Yellow Warning Box** - Devices that haven't reconnected yet
3. **Flash Messages** - Real-time status as you interact

### API Monitoring

```bash
# Check full status
curl http://localhost:8080/api/status | python3 -m json.tool

# Shows last_seen for each device
```

Example response:
```json
{
  "hardware_status": {
    "S2": {
      "device_id": "S2",
      "is_failed": true,
      "last_seen": "2h ago",
      "last_success_time": "2025-02-09T06:30:15",
      "last_error": "Cannot connect to Shelly",
      "can_retry": true
    }
  }
}
```

## 🔧 Manual Recovery Steps

If devices don't automatically reconnect:

### 1. Check Raspberry Pi
```bash
# Is service running?
sudo systemctl status irrigation.service

# If not, start it:
sudo systemctl start irrigation.service

# View logs
sudo journalctl -u irrigation.service -n 50
```

### 2. Check Shelly Devices
```bash
# Can you ping them?
ping 10.42.0.82  # S1
ping 10.42.0.56  # S2

# Test connection
curl "http://10.42.0.82/rpc/Shelly.GetDeviceInfo"

# Run diagnostic
cd ~/irrigation
python3 test_shelly.py
```

### 3. Check GPIO
```bash
# Are GPIO permissions OK?
groups | grep gpio

# If not in gpio group:
sudo usermod -a -G gpio $USER
```

## 🛡️ Preventing Issues

### 1. Set Static IPs for Shelly Devices

**Option A: Router DHCP Reservation**
1. Log into router
2. Find Shelly MAC addresses
3. Set reserved IPs:
   - S1: 10.42.0.82
   - S2: 10.42.0.56

**Option B: Shelly Static IP**
1. Go to `http://10.42.0.82`
2. Settings → Wi-Fi → Set static IP
3. Enter:
   - IP: 10.42.0.82
   - Netmask: 255.255.255.0
   - Gateway: 10.42.0.1

### 2. Configure Auto-Start

```bash
# Create systemd service
sudo cp irrigation.service /etc/systemd/system/

# Enable auto-start
sudo systemctl enable irrigation.service

# Test reboot
sudo reboot
```

After reboot, check:
```bash
sudo systemctl status irrigation.service
```

Should show: `Active: active (running)`

### 3. UPS (Uninterruptible Power Supply)

For critical installations:
- Small UPS (~500VA) for Raspberry Pi
- Keeps system running during brief outages
- Allows graceful shutdown on extended outage

### 4. Watchdog Timer

Enable hardware watchdog to auto-reboot if system hangs:

```bash
# Install watchdog
sudo apt-get install watchdog

# Enable it
sudo systemctl enable watchdog
sudo systemctl start watchdog
```

## 📝 Post-Outage Checklist

After power is restored:

- [ ] Check irrigation service is running
- [ ] Verify all zones show "last seen" recently
- [ ] Test one zone manually (ON/OFF)
- [ ] Check upcoming schedules are correct
- [ ] Review logs for any errors
- [ ] Note any permanently failed devices

## 🔍 Understanding Last-Seen Times

| Last Seen | Meaning | Action |
|-----------|---------|--------|
| "30s ago" | Normal, just contacted | ✅ OK |
| "5m ago" | Normal, not used recently | ✅ OK |
| "2h ago" | May have been off | ⚠️ Check device |
| "1d ago" | Device likely offline | ❌ Investigate |
| "Never" | New device or always failed | ❌ Check config |

## 🎯 What Gets Preserved

### ✅ Survives Power Outage
- Schedules (saved in schedules.json)
- Configuration (config.py)
- Error logs
- Skip history (humidity-based)

### ❌ Lost on Power Outage
- Currently running program (stops)
- In-memory cache (rebuilt on startup)
- Active GPIO state (resets to OFF)

## 💡 Example Scenario

**Before Outage (14:00)**:
- S1 working: "Last seen: 30s ago"
- S2 working: "Last seen: 1m ago"
- R1 working: "Last seen: 5m ago"

**Power lost (14:15)**

**Power returns (16:45)**:
- S1: "Last seen: 2h ago" → reconnects in 90s → "Last seen: 30s ago"
- S2: "Last seen: 2h ago" → still offline → stays "2h ago"
- R1: "Last seen: 2h ago" → works immediately → "Last seen: 10s ago"

The "2h ago" tells you the device WAS working before outage!

## 🆘 Emergency Contact Info

If system doesn't recover:

1. **Check this guide first**
2. **Run diagnostics**: `python3 test_shelly.py`
3. **Check logs**: `tail -100 ~/irrigation/waterapp.log`
4. **Review API**: `curl localhost:8080/api/status`

## 📱 Notification Setup (Future)

You could add:
- Email alerts when devices go offline
- SMS for critical errors
- Telegram/WhatsApp bot for status

This requires additional setup but the hardware status tracking is already in place!

---

**Your system is now resilient to power outages and will clearly show you what's working and what needs attention!**
