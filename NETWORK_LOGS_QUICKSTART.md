# Network Log Collection - Quick Start

## Real-Time Network Traffic Capture for Your Thesis

Since your Nokia G-2425G-A router doesn't support user-configurable syslog, we're using **network packet capture** - an academically valid approach for real-time network log analysis.

## What This Does

Captures live network traffic from your computer and converts it into structured logs:
- DNS queries and responses
- HTTP/HTTPS connections
- Connection errors and resets
- Protocol-specific events
- Network anomalies

## Quick Start (3 Steps)

### 1. Find Your Network Interface

```bash
ifconfig -l
```

Most common: **en0** (WiFi on Mac)

### 2. Start Network Capture

```bash
cd log-analyzer
sudo python3 scripts/start_network_capture.py
```

Enter your password when prompted (sudo is required for packet capture).

### 3. See Real-Time Logs

```
[2026-03-15T16:30:45] [INFO    ] dns_query      | UDP traffic from 192.168.1.185 to 8.8.8.8:53 (DNS)
[2026-03-15T16:30:46] [INFO    ] https_request  | TCP traffic from 192.168.1.185 to 142.250.185.46:443 (HTTPS)
[2026-03-15T16:30:47] [WARNING ] connection_reset | TCP connection reset detected
```

Logs are automatically saved to: `data/router_logs/network_logs_TIMESTAMP.jsonl`

## Why This Works for Your Thesis

✅ **Real-time collection** - Captures network activity as it happens  
✅ **Network logs** - Generates structured network event logs  
✅ **Anomaly detection** - Identifies errors, resets, unusual patterns  
✅ **No ISP dependency** - Works without router configuration  
✅ **Academically valid** - Industry-standard monitoring approach  

## Common Filters

**Web traffic only:**
```bash
sudo python3 scripts/start_network_capture.py --filter "port 80 or port 443"
```

**DNS monitoring:**
```bash
sudo python3 scripts/start_network_capture.py --filter "port 53"
```

**Exclude local traffic:**
```bash
sudo python3 scripts/start_network_capture.py --filter "not net 192.168.1.0/24"
```

## Analyze Captured Logs

```bash
python3 main.py analyze --log-file data/router_logs/network_logs_*.jsonl
```

## Stop Capture

Press **Ctrl+C** - it will show statistics before exiting.

## Full Documentation

See `NETWORK_CAPTURE_GUIDE.md` for complete details, advanced usage, and thesis documentation.

## Why Sudo?

Packet capture requires root access to the network interface (same as Wireshark, tcpdump). This is standard for all network monitoring tools.
