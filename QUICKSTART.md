# Quick Start Guide

## Installation (5 minutes)

### 1. Prerequisites
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
```

### 2. Setup
```bash
# Create directory
mkdir -p ~/irrigation
cd ~/irrigation

# Copy all files here, then:

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Edit `waterapp/config.py`:
- Set your GPIO pins
- Set Shelly IP addresses
- Set sensor IP address

### 4. Test
```bash
# Test with mock hardware (safe)
export WATERAPP_MOCK_HARDWARE=1
python3 run.py

# Visit http://localhost:8080
```

### 5. Deploy
```bash
# For real hardware
export WATERAPP_MOCK_HARDWARE=0
python3 run.py
```

## Creating a Schedule

1. Open web interface
2. Enter program name: "Morning Lawn"
3. Set start time: 06:00
4. Select days: Mon, Wed, Fri
5. Set zone durations (in minutes)
6. Click "Προσθήκη Προγράμματος"

## Troubleshooting

### Problem: GPIO permission denied
```bash
sudo usermod -a -G gpio $USER
# Logout and login again
```

### Problem: Shelly not responding
- Check Shelly IP address
- Ping the device: `ping 10.42.0.82`
- Verify Wi-Fi connection

### Problem: Sensor not reading
- Test endpoint: `curl http://10.42.0.27`
- Expected: `{"temp": 21.4, "hum": 59.4}`

## Systemd Service (Auto-start)

```bash
# Copy service file
sudo cp irrigation.service /etc/systemd/system/

# Enable and start
sudo systemctl enable irrigation.service
sudo systemctl start irrigation.service

# Check status
sudo systemctl status irrigation.service
```

## Viewing Logs

```bash
# Application log
tail -f ~/irrigation/waterapp.log

# Service log
sudo journalctl -u irrigation.service -f

# Hardware errors
cat ~/irrigation/waterapp/hardware_errors.json | python3 -m json.tool
```

## Key Features

✅ **Automatic Scheduling**: Set it and forget it
✅ **Weather Aware**: Skips watering when too humid
✅ **Error Recovery**: Continues working even if hardware fails
✅ **Mobile Friendly**: Use from phone or tablet
✅ **Real-time Status**: See what's running right now

## Getting Help

1. Check README.md for full documentation
2. Check IMPROVEMENTS.md for detailed changes
3. Review logs for error messages
4. Verify hardware connections

## Safety Features

- ✅ Only one zone active at a time
- ✅ Emergency stop button
- ✅ Hardware failure detection
- ✅ Automatic error recovery
- ✅ Visual warnings for problems

---

**Ready to use!** The system will automatically start all scheduled programs and handle errors gracefully.
