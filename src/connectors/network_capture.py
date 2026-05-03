"""
Network Traffic Capture for Real-Time Log Generation
Captures network packets and converts them to structured logs
"""

import subprocess
import threading
import re
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from queue import Queue
import json
import socket

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NetworkLog:
    """Structured network log entry"""
    timestamp: str
    severity: str
    event_type: str
    source_ip: str
    dest_ip: str
    source_port: Optional[int]
    dest_port: Optional[int]
    protocol: str
    message: str
    metadata: Dict[str, Any]


class NetworkCapture:
    """
    Real-time network traffic capture and log generation
    Uses tcpdump for packet capture (available on macOS by default)
    """
    
    # Common ports and their services
    COMMON_PORTS = {
        20: 'FTP-DATA', 21: 'FTP', 22: 'SSH', 23: 'Telnet',
        25: 'SMTP', 53: 'DNS', 67: 'DHCP', 68: 'DHCP',
        80: 'HTTP', 110: 'POP3', 143: 'IMAP', 443: 'HTTPS',
        445: 'SMB', 465: 'SMTPS', 587: 'SMTP', 993: 'IMAPS',
        995: 'POP3S', 3306: 'MySQL', 3389: 'RDP', 5432: 'PostgreSQL',
        8080: 'HTTP-Proxy', 8443: 'HTTPS-Alt'
    }
    
    # Severity mapping based on event type
    SEVERITY_MAP = {
        'connection_refused': 'WARNING',
        'connection_reset': 'WARNING',
        'dns_query': 'INFO',
        'dns_response': 'INFO',
        'http_request': 'INFO',
        'https_request': 'INFO',
        'ssh_connection': 'NOTICE',
        'failed_connection': 'WARNING',
        'port_scan': 'WARNING',
        'unusual_traffic': 'NOTICE',
        'connection_established': 'INFO',
        'connection_closed': 'INFO'
    }
    
    def __init__(
        self,
        interface: str = 'en0',
        callback: Optional[Callable[[NetworkLog], None]] = None,
        filter_expression: Optional[str] = None
    ):
        """
        Initialize network capture
        
        Args:
            interface: Network interface to capture (en0 for WiFi on Mac)
            callback: Function to call when a log is generated
            filter_expression: tcpdump filter (e.g., 'port 80 or port 443')
        """
        self.interface = interface
        self.callback = callback
        self.filter_expression = filter_expression or 'tcp or udp or icmp'
        
        self.running = False
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.log_queue = Queue()
        
        # Statistics
        self.stats = {
            'packets_captured': 0,
            'logs_generated': 0,
            'started_at': None,
            'last_capture': None
        }
        
        logger.info(f"NetworkCapture initialized on interface {interface}")
    
    def get_service_name(self, port: int) -> str:
        """Get service name for port"""
        return self.COMMON_PORTS.get(port, f'port-{port}')
    
    def parse_tcpdump_line(self, line: str) -> Optional[NetworkLog]:
        """
        Parse tcpdump output line into NetworkLog
        Example: 16:30:45.123456 IP 192.168.1.100.54321 > 8.8.8.8.53: UDP, length 45
        """
        try:
            # Extract timestamp
            timestamp_match = re.match(r'^(\d{2}:\d{2}:\d{2}\.\d+)', line)
            if not timestamp_match:
                return None
            
            time_str = timestamp_match.group(1)
            timestamp = datetime.now().strftime('%Y-%m-%d') + 'T' + time_str.split('.')[0]
            
            # Extract protocol
            protocol = 'UNKNOWN'
            if ' IP ' in line or ' IP6 ' in line:
                if ' UDP' in line:
                    protocol = 'UDP'
                elif ' tcp ' in line.lower() or 'Flags' in line:
                    protocol = 'TCP'
                elif ' ICMP' in line:
                    protocol = 'ICMP'
            
            # Extract source and destination
            # Format: IP src.port > dst.port
            ip_match = re.search(
                r'IP6?\s+([0-9a-f.:]+)\.(\d+)\s*>\s*([0-9a-f.:]+)\.(\d+)',
                line
            )
            
            if ip_match:
                src_ip = ip_match.group(1)
                src_port = int(ip_match.group(2))
                dst_ip = ip_match.group(3)
                dst_port = int(ip_match.group(4))
            else:
                # Try without ports (ICMP, etc.)
                ip_match = re.search(
                    r'IP6?\s+([0-9a-f.:]+)\s*>\s*([0-9a-f.:]+)',
                    line
                )
                if ip_match:
                    src_ip = ip_match.group(1)
                    dst_ip = ip_match.group(2)
                    src_port = None
                    dst_port = None
                else:
                    return None
            
            # Determine event type and severity
            event_type = 'network_traffic'
            severity = 'INFO'
            
            # DNS traffic
            if dst_port == 53 or src_port == 53:
                event_type = 'dns_query' if dst_port == 53 else 'dns_response'
                severity = 'INFO'
            
            # HTTP/HTTPS
            elif dst_port in [80, 8080]:
                event_type = 'http_request'
                severity = 'INFO'
            elif dst_port == 443:
                event_type = 'https_request'
                severity = 'INFO'
            
            # SSH
            elif dst_port == 22 or src_port == 22:
                event_type = 'ssh_connection'
                severity = 'NOTICE'
            
            # Connection flags
            if 'Flags [R]' in line:  # Reset
                event_type = 'connection_reset'
                severity = 'WARNING'
            elif 'Flags [S]' in line:  # SYN
                event_type = 'connection_attempt'
                severity = 'INFO'
            elif 'Flags [F]' in line:  # FIN
                event_type = 'connection_closed'
                severity = 'INFO'
            
            # Build message
            service_name = self.get_service_name(dst_port) if dst_port else protocol
            message = f"{protocol} traffic from {src_ip}"
            if src_port:
                message += f":{src_port}"
            message += f" to {dst_ip}"
            if dst_port:
                message += f":{dst_port} ({service_name})"
            
            # Extract additional info
            length_match = re.search(r'length (\d+)', line)
            length = int(length_match.group(1)) if length_match else None
            
            metadata = {
                'raw_line': line,
                'packet_length': length,
                'interface': self.interface
            }
            
            return NetworkLog(
                timestamp=timestamp,
                severity=severity,
                event_type=event_type,
                source_ip=src_ip,
                dest_ip=dst_ip,
                source_port=src_port,
                dest_port=dst_port,
                protocol=protocol,
                message=message,
                metadata=metadata
            )
            
        except Exception as e:
            logger.debug(f"Error parsing line: {e}")
            return None
    
    def _capture_loop(self):
        """Main capture loop running in separate thread"""
        logger.info(f"Starting packet capture on {self.interface}")
        
        # Build tcpdump command
        # -l: line buffered output
        # -n: don't resolve hostnames
        # -i: interface
        cmd = [
            'tcpdump',
            '-l',
            '-n',
            '-i', self.interface,
            self.filter_expression
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            logger.info(f"tcpdump started with PID {self.process.pid}")
            
            # Read output line by line
            for line in self.process.stdout:
                if not self.running:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                self.stats['packets_captured'] += 1
                self.stats['last_capture'] = datetime.now().isoformat()
                
                # Parse into log
                log = self.parse_tcpdump_line(line)
                
                if log:
                    self.stats['logs_generated'] += 1
                    self.log_queue.put(log)
                    
                    # Call callback
                    if self.callback:
                        try:
                            self.callback(log)
                        except Exception as e:
                            logger.error(f"Error in callback: {e}")
            
        except Exception as e:
            if self.running:
                logger.error(f"Error in capture loop: {e}")
        finally:
            if self.process:
                self.process.terminate()
    
    def start(self):
        """Start packet capture"""
        if self.running:
            logger.warning("Network capture already running")
            return
        
        # Check if tcpdump is available
        try:
            subprocess.run(['which', 'tcpdump'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.error("tcpdump not found. Please install it.")
            raise RuntimeError("tcpdump not available")
        
        self.running = True
        self.stats['started_at'] = datetime.now().isoformat()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        
        # Wait briefly to verify tcpdump started successfully
        import time
        time.sleep(0.5)
        if self.process and self.process.poll() is not None:
            self.running = False
            stderr_output = self.process.stderr.read() if self.process.stderr else ''
            logger.error(f"tcpdump failed immediately: {stderr_output}")
            if 'permission' in stderr_output.lower() or 'denied' in stderr_output.lower():
                raise PermissionError("tcpdump requires root privileges to capture network packets.")
            raise RuntimeError(f"tcpdump failed to start: {stderr_output.strip()}")
        
        logger.info(f"Network capture started on {self.interface}")
    
    def stop(self):
        """Stop packet capture"""
        if not self.running:
            return
        
        logger.info("Stopping network capture...")
        self.running = False
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("Network capture stopped")
    
    def get_log(self, timeout: Optional[float] = None) -> Optional[NetworkLog]:
        """Get next log from queue"""
        try:
            return self.log_queue.get(timeout=timeout)
        except:
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get capture statistics"""
        stats = self.stats.copy()
        if stats['started_at']:
            uptime = (
                datetime.now() - 
                datetime.fromisoformat(stats['started_at'])
            ).total_seconds()
            stats['uptime_seconds'] = uptime
            stats['packets_per_second'] = (
                stats['packets_captured'] / uptime if uptime > 0 else 0
            )
        return stats


class NetworkLogCollector:
    """
    High-level network log collector
    Integrates with the log analyzer system
    """
    
    def __init__(
        self,
        interface: str = 'en0',
        filter_expression: Optional[str] = None,
        log_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Initialize network log collector
        
        Args:
            interface: Network interface (en0 for WiFi on Mac)
            filter_expression: Packet filter
            log_callback: Callback for processed logs
        """
        self.capture = NetworkCapture(
            interface=interface,
            filter_expression=filter_expression,
            callback=self._process_network_log
        )
        self.log_callback = log_callback
        self.collected_logs = []
        self.recent_logs = []  # Keep last 100 logs for API access
        
        logger.info(f"NetworkLogCollector initialized on {interface}")
    
    def _process_network_log(self, log: NetworkLog):
        """Process captured network log into standard format"""
        try:
            # Convert to standard log format
            log_entry = {
                'content': log.message,
                'timestamp': log.timestamp,
                'severity': log.severity,
                'source_type': 'network',
                'event_type': log.event_type,
                'src_ip': log.source_ip,
                'dst_ip': log.dest_ip,
                'src_port': log.source_port,
                'dst_port': log.dest_port,
                'protocol': log.protocol,
                'metadata': log.metadata
            }
            
            # Store locally
            self.collected_logs.append(log_entry)
            
            # Keep recent logs (last 100)
            self.recent_logs.append(log_entry)
            if len(self.recent_logs) > 100:
                self.recent_logs = self.recent_logs[-100:]
            
            # Call external callback
            if self.log_callback:
                self.log_callback(log_entry)
            
        except Exception as e:
            logger.error(f"Error processing network log: {e}")
    
    def start(self):
        """Start collecting network logs"""
        self.capture.start()
        logger.info("Network log collector started")
    
    def stop(self):
        """Stop collecting network logs"""
        self.capture.stop()
        logger.info("Network log collector stopped")
    
    def get_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get collected logs"""
        if limit:
            return self.collected_logs[-limit:]
        return self.collected_logs
    
    def clear_logs(self):
        """Clear collected logs"""
        self.collected_logs.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics"""
        stats = self.capture.get_stats()
        stats['logs_stored'] = len(self.collected_logs)
        return stats
