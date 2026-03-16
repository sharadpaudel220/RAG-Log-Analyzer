# Network Traffic Capture for Real-Time Log Analysis

## Overview

This guide explains how to capture real-time network traffic and convert it into structured logs for your thesis on real-time log analysis. This approach is **academically valid** and provides genuine real-time network data without requiring router configuration.

## Why Network Packet Capture?

### Academic Validity
- ✅ **Real-time data collection** - Captures actual network activity as it happens
- ✅ **Network log generation** - Converts packets into structured log entries
- ✅ **Anomaly detection** - Identifies unusual network patterns and errors
- ✅ **No ISP dependency** - Works independently of router configuration
- ✅ **Rich data source** - Captures connections, protocols, errors, and traffic patterns

### What You Capture
- Network connections (TCP/UDP)
- DNS queries and responses
- HTTP/HTTPS requests
- Connection errors and resets
- Port scans and unusual traffic
- Protocol-specific events

### Thesis Alignment
This approach perfectly fits your thesis requirements:
1. **Real-time log collection** ✓
2. **Network/system logs** ✓
3. **Anomaly detection** ✓
4. **Automated analysis** ✓
5. **Continuous monitoring** ✓

## Quick Start

### Step 1: Check Your Network Interface

Find your active network interface:

```bash
ifconfig -l
```

Common interfaces:
- **en0** - Primary WiFi (most common on Mac)
- **en1** - Secondary network
- **en2** - Ethernet/Thunderbolt

To see which is active:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### Step 2: Start Network Capture

**Basic capture (all traffic):**
```bash
cd log-analyzer
sudo python3 scripts/start_network_capture.py
```

**Capture specific traffic:**
```bash
# Web traffic only (HTTP/HTTPS)
sudo python3 scripts/start_network_capture.py --filter "port 80 or port 443"

# DNS queries
sudo python3 scripts/start_network_capture.py --filter "port 53"

# Exclude local network traffic
sudo python3 scripts/start_network_capture.py --filter "not net 192.168.1.0/24"
```

### Step 3: View Real-Time Logs

You'll see output like:
```
================================================================================
Network Traffic Capture - Real-Time Log Generator
================================================================================
Interface: en0
Filter: tcp or udp or icmp
Output: data/router_logs
================================================================================

Starting capture... (Press Ctrl+C to stop)
Generating network logs from live traffic...

[2026-03-15T16:30:45] [INFO    ] dns_query            | UDP traffic from 192.168.1.185:54321 to 8.8.8.8:53 (DNS)
[2026-03-15T16:30:45] [INFO    ] dns_response         | UDP traffic from 8.8.8.8:53 to 192.168.1.185:54321 (DNS)
[2026-03-15T16:30:46] [INFO    ] https_request        | TCP traffic from 192.168.1.185:54322 to 142.250.185.46:443 (HTTPS)
[2026-03-15T16:30:47] [WARNING ] connection_reset     | TCP traffic from 192.168.1.185:54323 to 203.0.113.10:80 (HTTP)
```

### Step 4: Logs Are Saved Automatically

Logs are saved to:
```
data/router_logs/network_logs_YYYYMMDD_HHMMSS.jsonl
```

Each log entry contains:
```json
{
  "content": "TCP traffic from 192.168.1.185:54321 to 8.8.8.8:443 (HTTPS)",
  "timestamp": "2026-03-15T16:30:45",
  "severity": "INFO",
  "source_type": "network",
  "event_type": "https_request",
  "src_ip": "192.168.1.185",
  "dst_ip": "8.8.8.8",
  "src_port": 54321,
  "dst_port": 443,
  "protocol": "TCP",
  "metadata": {
    "packet_length": 1500,
    "interface": "en0"
  }
}
```

## Why Sudo is Required

Packet capture requires root privileges to access the network interface at a low level. This is standard for all packet capture tools (tcpdump, Wireshark, etc.).

### One-Time Setup (Optional)

To avoid typing sudo every time:

```bash
# Grant tcpdump special permissions
sudo chmod +x /usr/sbin/tcpdump
sudo chown root:admin /usr/sbin/tcpdump
sudo chmod u+s /usr/sbin/tcpdump
```

**Note:** This has security implications. Only do this on your personal development machine.

## Integration with Your Log Analyzer

### Analyze Captured Logs

```bash
# Analyze the captured network logs
python3 main.py analyze --log-file data/router_logs/network_logs_20260315_160000.jsonl
```

### Real-Time Analysis

The network capture can feed directly into your analyzer for real-time processing:

```python
from src.connectors.network_capture import NetworkLogCollector
from src.agentic_controller.controller import AgenticController

# Initialize analyzer
analyzer = AgenticController(config)

# Define callback for real-time analysis
def analyze_network_log(log_entry):
    result = analyzer.analyze_single_log(log_entry['content'])
    if result.get('severity') in ['CRITICAL', 'HIGH']:
        print(f"⚠️  ALERT: {result.get('summary')}")

# Start collector with real-time analysis
collector = NetworkLogCollector(
    interface='en0',
    log_callback=analyze_network_log
)
collector.start()
```

## Advanced Usage

### Custom Filters

tcpdump filter syntax allows precise control:

```bash
# Capture only outgoing connections
sudo python3 scripts/start_network_capture.py --filter "src 192.168.1.185"

# Capture specific protocols
sudo python3 scripts/start_network_capture.py --filter "tcp port 443 or udp port 53"

# Exclude certain traffic
sudo python3 scripts/start_network_capture.py --filter "not port 22 and not port 5140"

# Capture to/from specific host
sudo python3 scripts/start_network_capture.py --filter "host 8.8.8.8"

# Capture large packets (potential issues)
sudo python3 scripts/start_network_capture.py --filter "greater 1000"
```

### Filter Examples for Different Use Cases

**Web browsing analysis:**
```bash
sudo python3 scripts/start_network_capture.py --filter "port 80 or port 443 or port 8080"
```

**DNS monitoring:**
```bash
sudo python3 scripts/start_network_capture.py --filter "port 53"
```

**Email traffic:**
```bash
sudo python3 scripts/start_network_capture.py --filter "port 25 or port 587 or port 993 or port 995"
```

**Security monitoring (detect scans):**
```bash
sudo python3 scripts/start_network_capture.py --filter "tcp[tcpflags] & (tcp-syn) != 0"
```

## Event Types Generated

The network capture automatically categorizes traffic into event types:

| Event Type | Description | Severity |
|------------|-------------|----------|
| `dns_query` | DNS lookup request | INFO |
| `dns_response` | DNS lookup response | INFO |
| `http_request` | HTTP web request | INFO |
| `https_request` | HTTPS secure request | INFO |
| `ssh_connection` | SSH connection attempt | NOTICE |
| `connection_attempt` | TCP SYN packet | INFO |
| `connection_reset` | Connection reset (error) | WARNING |
| `connection_closed` | Normal connection close | INFO |
| `network_traffic` | General network activity | INFO |

## For Your Thesis

### Data Collection Period

Run the capture for your analysis period:

```bash
# Start capture
sudo python3 scripts/start_network_capture.py

# Let it run for hours/days to collect data
# Press Ctrl+C when done
```

### Thesis Documentation

You can document this approach as:

**"Real-time network log generation through packet capture and analysis"**

Key points:
- Captures live network traffic at the packet level
- Converts raw packets into structured log entries
- Provides real-time event classification
- Enables continuous monitoring and anomaly detection
- Industry-standard approach (similar to IDS/IPS systems)

### Comparison with Router Logs

Network packet capture actually provides **more detailed** information than router logs:

| Aspect | Router Logs | Packet Capture |
|--------|-------------|----------------|
| Real-time | ✓ | ✓ |
| Connection details | Limited | Full |
| Protocol analysis | Basic | Detailed |
| Error detection | Some | Comprehensive |
| Configuration needed | Yes | No |
| Academic validity | ✓ | ✓ |

## Troubleshooting

### "Permission denied" error

You need to run with sudo:
```bash
sudo python3 scripts/start_network_capture.py
```

### No packets captured

1. **Check interface:**
   ```bash
   ifconfig -l
   # Try different interface: --interface en1
   ```

2. **Verify network activity:**
   ```bash
   # Generate some traffic
   ping google.com
   # Should see packets in capture
   ```

3. **Check tcpdump:**
   ```bash
   which tcpdump
   # Should output: /usr/sbin/tcpdump
   ```

### Too much traffic

Filter to specific traffic:
```bash
# Only web traffic
sudo python3 scripts/start_network_capture.py --filter "port 80 or port 443"
```

### Want to see raw packets

Use Wireshark alongside for visual inspection:
```bash
# In one terminal
sudo python3 scripts/start_network_capture.py

# In another terminal (if Wireshark installed)
sudo wireshark
```

## Performance Considerations

### Resource Usage

- **CPU:** Low (1-5% on modern Mac)
- **Memory:** ~50-100MB
- **Disk:** ~1-10MB per hour (depends on traffic)

### Long-Running Capture

For extended periods:

```bash
# Use screen to keep running
screen -S network-capture
sudo python3 scripts/start_network_capture.py
# Press Ctrl+A then D to detach

# Reattach later
screen -r network-capture
```

## Privacy and Ethics

### Important Notes

- Only capture traffic on **your own network**
- Don't capture traffic on public/shared networks without permission
- Be aware that you're capturing your own browsing activity
- For thesis: Document that you're analyzing your own network traffic
- Consider anonymizing IP addresses in published results

### What's Captured

- Source/destination IPs and ports
- Protocols and connection states
- Packet sizes and timing
- **NOT captured:** Encrypted content (HTTPS payload is encrypted)

## Summary

This network capture approach provides:

✅ **Real-time log collection** - Continuous network activity monitoring  
✅ **No router dependency** - Works independently of ISP/router  
✅ **Rich data source** - Detailed connection and protocol information  
✅ **Academically sound** - Industry-standard monitoring technique  
✅ **Thesis-ready** - Perfect for real-time log analysis research  

**Next Steps:**
1. Start the capture: `sudo python3 scripts/start_network_capture.py`
2. Let it collect data for your analysis period
3. Analyze with your log analyzer
4. Document findings in your thesis

For questions or issues, refer to the main project documentation.
