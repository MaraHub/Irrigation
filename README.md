# Automated Irrigation Control System

A robust, production-ready irrigation control system for Raspberry Pi with GPIO relays and Shelly smart switches. Features comprehensive error handling, hardware failure recovery, and a user-friendly web interface.

## 🌟 Features

### Core Functionality
- **Multi-Zone Control**: Manages both GPIO relays and Shelly Wi-Fi switches
- **Automated Scheduling**: Time-based irrigation with day-of-week selection
- **Smart Humidity Sensing**: Automatically skips irrigation when humidity is too high
- **Manual Override**: Direct control of individual zones via web interface
- **Exclusive Operation**: Only one zone can be active at a time (prevents water pressure issues)

### Error Handling & Reliability
- **Hardware Failure Detection**: Automatically detects and reports non-responsive devices
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Error Logging**: Comprehensive logging of all hardware errors
- **Graceful Degradation**: System continues operating even if some devices fail
- **Recovery Mechanisms**: Automatic reconnection attempts for failed hardware

### User Interface
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Real-Time Status**: Live display of current irrigation operations
- **Error Notifications**: Clear, actionable error messages in Greek
- **Hardware Status Monitoring**: Visual indicators for failed devices
- **Sensor Display**: Current temperature and humidity readings

## 📋 System Requirements

### Hardware
- Raspberry Pi (tested on Pi 3B+ and Pi 4)
- Relay HAT or individual relay modules (5V, active-low)
- Shelly Plus 1/1PM or similar Wi-Fi switches
- DHT22/AM2302 humidity sensor (or ESP8266 with sensor)
- Stable 5V power supply for Raspberry Pi
- Network connectivity (Wi-Fi or Ethernet)

### Software
- Raspberry Pi OS (Bullseye or newer)
- Python 3.8 or higher
- Internet connection for initial setup

## 🚀 Installation

### 1. System Preparation

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
sudo apt-get install -y python3-pip python3-venv git
```

### 2. Clone or Copy Files

```bash
# Create application directory
sudo mkdir -p /home/ic/irrigation
cd /home/ic/irrigation

# Copy application files here
# (or clone from repository if available)
```

### 3. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install flask requests RPi.GPIO
```

### 4. Configuration

Edit `waterapp/config.py` to match your hardware:

```python
# GPIO pins for relays (BCM numbering)
RELAYS = {
    "R1": 26,  # GPIO26
    "R2": 20,  # GPIO20
    "R3": 21,  # GPIO21
}

# Shelly device IPs
SHELLY_ZONES = {
    "S1": {
        "ip": "10.42.0.82",  # Change to your Shelly's IP
        "rpc_id": 0,
        "name": "New Gazon",
    },
}

# Humidity sensor IP
SENSOR_IP = "10.42.0.27"  # Change to your sensor's IP

# Humidity threshold (skip irrigation if above this)
HUMIDITY_SKIP_THRESHOLD = 95.0
```

### 5. Test the Application

```bash
# Run in development mode (with mock hardware)
export WATERAPP_MOCK_HARDWARE=1
python3 run.py
```

Visit `http://localhost:8080` in your browser to verify the interface loads correctly.

### 6. Production Deployment

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/irrigation.service
```

Add the following content:

```ini
[Unit]
Description=Automated Irrigation Control System
After=network.target

[Service]
Type=simple
User=ic
WorkingDirectory=/home/ic/irrigation
Environment="WATERAPP_MOCK_HARDWARE=0"
ExecStart=/home/ic/irrigation/venv/bin/python3 /home/ic/irrigation/run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable irrigation.service
sudo systemctl start irrigation.service

# Check status
sudo systemctl status irrigation.service

# View logs
sudo journalctl -u irrigation.service -f
```

## 📖 Usage Guide

### Accessing the Interface

Open a web browser and navigate to:
- Local: `http://localhost:8080`
- Network: `http://<raspberry-pi-ip>:8080`

### Manual Control

1. **Turn Zone ON**: Click the "ON" button for a specific zone
2. **Turn Zone OFF**: Click the "OFF" button
3. **Pulse Mode**: Enter seconds and click "PULSE" to run for a specific duration
4. **Emergency Stop**: Click "Κλείσιμο Όλων των Ζωνών" to shut off everything

### Creating Schedules

1. Enter a program name (e.g., "Morning Lawn")
2. Set start time in 24-hour format (e.g., 06:00)
3. Select days of the week
4. Set duration in minutes for each zone
5. Click "Προσθήκη Προγράμματος" to save

### Monitoring

- **Current Status**: Shows which zone is active and when it will finish
- **Last Run**: Displays the most recent scheduled execution
- **Environment**: Temperature and humidity readings
- **Failed Devices**: Warnings appear for non-responsive hardware

## 🔧 Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WATERAPP_MOCK_HARDWARE` | `1` | Set to `0` to use real hardware |
| `SECRET_KEY` | (generated) | Flask secret key for sessions |

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CHECK_INTERVAL_SEC` | 10 | How often to check schedules (seconds) |
| `HUMIDITY_SKIP_THRESHOLD` | 95.0 | Skip irrigation if humidity above this (%) |
| `SENSOR_TIMEOUT` | 10.0 | Sensor request timeout (seconds) |
| `MAX_CONSECUTIVE_ERRORS` | 3 | Errors before marking device as failed |
| `HARDWARE_RETRY_COOLDOWN` | 300 | Retry interval for failed devices (seconds) |

## 🐛 Troubleshooting

### Common Issues

#### 1. GPIO Permission Denied

```bash
# Add user to gpio group
sudo usermod -a -G gpio ic

# Reboot or re-login
sudo reboot
```

#### 2. Shelly Device Not Responding

- Verify Shelly is powered on and connected to Wi-Fi
- Check IP address hasn't changed (use DHCP reservation)
- Ping the device: `ping 10.42.0.82`
- Check Shelly firmware is up to date

#### 3. Sensor Not Reading

- Verify sensor device is powered and running
- Check network connectivity
- Test sensor endpoint: `curl http://10.42.0.27`
- Expected JSON format: `{"temp": 21.4, "hum": 59.4}`

#### 4. Schedules Not Running

- Check system time: `date`
- Verify schedule file exists: `ls -la ~/irrigation/waterapp/schedules.json`
- Check logs: `journalctl -u irrigation.service -n 100`
- Ensure days are correctly selected (Mon, Tue, Wed, etc.)

### Viewing Logs

```bash
# Application logs
cat /home/ic/irrigation/waterapp.log

# Systemd service logs
sudo journalctl -u irrigation.service -f

# Hardware errors
cat /home/ic/irrigation/waterapp/hardware_errors.json

# Skipped runs (high humidity)
cat /home/ic/irrigation/waterapp/skipped_runs.json
```

## 📁 File Structure

```
waterapp/
├── run.py                 # Application entry point
├── waterapp/
│   ├── __init__.py       # Flask app factory
│   ├── config.py         # Configuration settings
│   ├── hardware.py       # Hardware abstraction layer
│   ├── sensor.py         # Humidity sensor interface
│   ├── scheduler.py      # Background scheduler
│   ├── schedule_store.py # Schedule persistence
│   ├── state.py          # Shared state management
│   ├── views.py          # Flask routes/views
│   ├── templates/
│   │   ├── index.html    # Main dashboard
│   │   └── error.html    # Error page
│   └── static/
│       └── css/
│           └── style.css # Stylesheets
├── schedules.json        # Stored schedules (auto-created)
├── skipped_runs.json     # Skip log (auto-created)
├── hardware_errors.json  # Error log (auto-created)
└── waterapp.log          # Application log (auto-created)
```

## 🔒 Security Considerations

1. **Network Access**: The web interface has no authentication. Deploy behind a firewall or add authentication middleware.
2. **File Permissions**: Ensure schedule files are only writable by the application user.
3. **GPIO Access**: Limit GPIO group membership to trusted users only.
4. **API Endpoints**: Consider rate limiting if exposing to the internet.

## 🆘 API Reference

### Status Endpoints

```bash
# System status
curl http://localhost:8080/api/status

# Hardware status
curl http://localhost:8080/api/hardware_errors

# Sensor status
curl http://localhost:8080/api/sensor
```

### Response Format

```json
{
  "current_run": {
    "active": true,
    "name": "Morning Lawn",
    "step": "2/3: R2 (10m)",
    "ends_at": "2025-02-09T07:45:00"
  },
  "environment": {
    "temp": 18.5,
    "hum": 72.3,
    "last_update": "2025-02-09T07:35:12"
  },
  "hardware_status": {
    "R1": {
      "is_failed": false,
      "consecutive_errors": 0
    }
  }
}
```

## 📝 Maintenance

### Regular Tasks

- **Weekly**: Check logs for hardware errors
- **Monthly**: Verify all zones are functioning correctly
- **Seasonally**: Adjust schedules and humidity thresholds

### Backup

```bash
# Backup schedules
cp ~/irrigation/waterapp/schedules.json ~/schedules_backup_$(date +%Y%m%d).json

# Backup configuration
cp ~/irrigation/waterapp/config.py ~/config_backup_$(date +%Y%m%d).py
```

## 🤝 Contributing

Improvements welcome! Key areas:
- Additional hardware support
- Authentication/authorization
- Mobile app integration
- Weather API integration
- Advanced scheduling (sunrise/sunset)

## 📄 License

This software is provided as-is for personal and educational use.

## 👤 Support

For issues or questions:
1. Check the troubleshooting section
2. Review application logs
3. Check hardware connections
4. Verify network connectivity

---

**Version**: 2.0  
**Last Updated**: February 2025  
**Author**: Irrigation System Team
