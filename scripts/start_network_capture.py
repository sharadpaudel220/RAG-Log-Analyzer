#!/usr/bin/env python3
"""
Network Traffic Capture Script
Captures real-time network traffic and generates structured logs
"""

import sys
import os
import signal
from pathlib import Path
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.connectors.network_capture import NetworkLogCollector
from src.utils.logger import get_logger
import json
from datetime import datetime

logger = get_logger(__name__)


class NetworkCaptureApp:
    """Standalone network capture application"""
    
    def __init__(
        self,
        interface: str = 'en0',
        filter_expr: str = None,
        output_dir: str = 'data/router_logs'
    ):
        self.interface = interface
        self.filter_expr = filter_expr
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize collector
        self.collector = NetworkLogCollector(
            interface=interface,
            filter_expression=filter_expr,
            log_callback=self.on_log_received
        )
        
        # Open log file
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_filename = f"network_logs_{timestamp}.jsonl"
        self.log_file = open(self.output_dir / log_filename, 'a')
        
        logger.info(f"Network capture initialized on {interface}")
    
    def on_log_received(self, log_entry: dict):
        """Callback when a network log is generated"""
        # Color code by severity
        colors = {
            'CRITICAL': '\033[91m',
            'ERROR': '\033[91m',
            'WARNING': '\033[93m',
            'NOTICE': '\033[94m',
            'INFO': '\033[92m',
            'DEBUG': '\033[90m'
        }
        reset = '\033[0m'
        
        timestamp = log_entry.get('timestamp', '')
        severity = log_entry.get('severity', 'INFO')
        event_type = log_entry.get('event_type', 'unknown')
        message = log_entry.get('content', '')
        
        color = colors.get(severity, '')
        
        # Print to console
        print(f"{color}[{timestamp}] [{severity:8s}] {event_type:20s} | {message}{reset}")
        
        # Save to file
        self.log_file.write(json.dumps(log_entry) + '\n')
        self.log_file.flush()
    
    def get_available_interfaces(self) -> list:
        """Get list of available network interfaces"""
        try:
            result = subprocess.run(
                ['ifconfig', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            interfaces = result.stdout.strip().split()
            return interfaces
        except:
            return ['en0', 'en1']
    
    def start(self):
        """Start the capture"""
        print("=" * 80)
        print("Network Traffic Capture - Real-Time Log Generator")
        print("=" * 80)
        print(f"Interface: {self.interface}")
        print(f"Filter: {self.filter_expr or 'All TCP/UDP/ICMP traffic'}")
        print(f"Output: {self.output_dir}")
        print("=" * 80)
        
        # Check if running with sudo
        if os.geteuid() != 0:
            print("\n⚠️  WARNING: Packet capture requires root privileges")
            print("Please run with sudo:")
            print(f"  sudo python3 {' '.join(sys.argv)}")
            print("\nOr grant tcpdump permissions:")
            print("  sudo chmod +x /usr/sbin/tcpdump")
            print("  sudo chown root:admin /usr/sbin/tcpdump")
            print("  sudo chmod u+s /usr/sbin/tcpdump")
            print("\n" + "=" * 80)
            return
        
        print("\nStarting capture... (Press Ctrl+C to stop)")
        print("Generating network logs from live traffic...\n")
        
        try:
            self.collector.start()
            
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Wait indefinitely
            while True:
                import time
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            logger.error(f"Error: {e}")
            self.stop()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\n\nShutting down...")
        self.stop()
        sys.exit(0)
    
    def stop(self):
        """Stop the capture"""
        print("\nStopping capture...")
        
        # Print statistics
        stats = self.collector.get_stats()
        print("\n" + "=" * 80)
        print("Statistics:")
        print(f"  Packets captured: {stats.get('packets_captured', 0)}")
        print(f"  Logs generated:   {stats.get('logs_generated', 0)}")
        print(f"  Logs stored:      {stats.get('logs_stored', 0)}")
        if 'uptime_seconds' in stats:
            print(f"  Uptime:           {stats['uptime_seconds']:.1f} seconds")
            print(f"  Rate:             {stats.get('packets_per_second', 0):.2f} packets/sec")
        print("=" * 80)
        
        self.collector.stop()
        self.log_file.close()
        
        print("Capture stopped.")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Network Traffic Capture - Real-Time Log Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture all traffic on WiFi interface (requires sudo)
  sudo python3 scripts/start_network_capture.py
  
  # Capture only HTTP/HTTPS traffic
  sudo python3 scripts/start_network_capture.py --filter "port 80 or port 443"
  
  # Capture DNS queries
  sudo python3 scripts/start_network_capture.py --filter "port 53"
  
  # Use different interface
  sudo python3 scripts/start_network_capture.py --interface en1

Common Filters:
  - Web traffic:     "port 80 or port 443"
  - DNS:             "port 53"
  - SSH:             "port 22"
  - Email:           "port 25 or port 587 or port 993"
  - Specific host:   "host 8.8.8.8"
  - Exclude local:   "not net 192.168.1.0/24"

Network Interfaces (macOS):
  - en0: Primary WiFi
  - en1: Secondary network
  - en2: Thunderbolt/USB Ethernet
  
Use 'ifconfig -l' to list all interfaces.

Note: This generates real-time network logs from packet capture.
      Perfect for thesis work on real-time log analysis.
        """
    )
    
    parser.add_argument(
        '--interface',
        default='en0',
        help='Network interface to capture (default: en0 for WiFi)'
    )
    parser.add_argument(
        '--filter',
        help='tcpdump filter expression (default: tcp or udp or icmp)'
    )
    parser.add_argument(
        '--output',
        default='data/router_logs',
        help='Output directory (default: data/router_logs)'
    )
    parser.add_argument(
        '--list-interfaces',
        action='store_true',
        help='List available network interfaces and exit'
    )
    
    args = parser.parse_args()
    
    # List interfaces if requested
    if args.list_interfaces:
        print("Available network interfaces:")
        try:
            result = subprocess.run(
                ['ifconfig', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            interfaces = result.stdout.strip().split()
            for iface in interfaces:
                print(f"  - {iface}")
        except:
            print("  Could not list interfaces")
        return
    
    # Create and start app
    app = NetworkCaptureApp(
        interface=args.interface,
        filter_expr=args.filter,
        output_dir=args.output
    )
    app.start()


if __name__ == '__main__':
    main()
