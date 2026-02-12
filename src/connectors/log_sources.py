"""
Log Source Connectors
Support for different log types and ingestion methods
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import hashlib

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LogSourceType(Enum):
    """Types of log sources"""
    SYSTEM = "system"           # OS system logs
    NETWORK = "network"         # Network device logs (routers, switches, firewalls)
    APPLICATION = "application" # Application logs
    SECURITY = "security"       # Security/audit logs
    DATABASE = "database"       # Database logs
    WEB_SERVER = "web_server"   # Web server logs (Apache, Nginx)
    CONTAINER = "container"     # Docker/Kubernetes logs
    CLOUD = "cloud"            # Cloud service logs (AWS, Azure, GCP)
    CUSTOM = "custom"          # Custom log sources


class IngestionMethod(Enum):
    """Methods for log ingestion"""
    API = "api"                 # REST API push
    WEBHOOK = "webhook"         # Webhook receiver
    FILE_UPLOAD = "file_upload" # File upload
    STREAMING = "streaming"     # Real-time streaming
    SYSLOG = "syslog"          # Syslog protocol
    AGENT = "agent"            # Log collection agent


@dataclass
class LogSource:
    """Configuration for a log source"""
    id: str
    name: str
    source_type: LogSourceType
    ingestion_method: IngestionMethod
    enabled: bool = True
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str = None
    last_received: Optional[str] = None
    total_logs_received: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type.value,
            'ingestion_method': self.ingestion_method.value,
            'enabled': self.enabled,
            'endpoint': self.endpoint,
            'filters': self.filters,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'last_received': self.last_received,
            'total_logs_received': self.total_logs_received
        }


class LogSourceManager:
    """Manage multiple log sources"""
    
    def __init__(self):
        self.sources: Dict[str, LogSource] = {}
        self.api_keys: Dict[str, str] = {}  # api_key -> source_id
        logger.info("LogSourceManager initialized")
    
    def generate_api_key(self, source_id: str) -> str:
        """Generate a unique API key for a source"""
        key_data = f"{source_id}:{datetime.now().isoformat()}"
        api_key = hashlib.sha256(key_data.encode()).hexdigest()[:32]
        self.api_keys[api_key] = source_id
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[str]:
        """Validate API key and return source_id"""
        return self.api_keys.get(api_key)
    
    def add_source(self, source: LogSource) -> bool:
        """Add a new log source"""
        try:
            if source.id in self.sources:
                logger.warning(f"Source {source.id} already exists")
                return False
            
            # Generate API key if needed
            if source.ingestion_method in [IngestionMethod.API, IngestionMethod.WEBHOOK]:
                if not source.api_key:
                    source.api_key = self.generate_api_key(source.id)
            
            self.sources[source.id] = source
            logger.info(f"Added log source: {source.name} ({source.source_type.value})")
            return True
        except Exception as e:
            logger.error(f"Error adding source: {e}")
            return False
    
    def remove_source(self, source_id: str) -> bool:
        """Remove a log source"""
        if source_id in self.sources:
            source = self.sources[source_id]
            if source.api_key and source.api_key in self.api_keys:
                del self.api_keys[source.api_key]
            del self.sources[source_id]
            logger.info(f"Removed log source: {source_id}")
            return True
        return False
    
    def get_source(self, source_id: str) -> Optional[LogSource]:
        """Get a log source by ID"""
        return self.sources.get(source_id)
    
    def get_source_by_api_key(self, api_key: str) -> Optional[LogSource]:
        """Get a log source by API key"""
        source_id = self.validate_api_key(api_key)
        if source_id:
            return self.sources.get(source_id)
        return None
    
    def list_sources(self, source_type: Optional[LogSourceType] = None) -> List[LogSource]:
        """List all sources, optionally filtered by type"""
        sources = list(self.sources.values())
        if source_type:
            sources = [s for s in sources if s.source_type == source_type]
        return sources
    
    def update_source_stats(self, source_id: str, log_count: int = 1):
        """Update source statistics"""
        if source_id in self.sources:
            source = self.sources[source_id]
            source.total_logs_received += log_count
            source.last_received = datetime.now().isoformat()
    
    def enable_source(self, source_id: str) -> bool:
        """Enable a log source"""
        if source_id in self.sources:
            self.sources[source_id].enabled = True
            return True
        return False
    
    def disable_source(self, source_id: str) -> bool:
        """Disable a log source"""
        if source_id in self.sources:
            self.sources[source_id].enabled = False
            return True
        return False


class LogFormatter:
    """Format logs from different sources into standard format"""
    
    @staticmethod
    def format_system_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format system logs (syslog format)"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('severity', 'INFO'),
            'hostname': raw_log.get('hostname'),
            'process': raw_log.get('process'),
            'pid': raw_log.get('pid'),
            'source_type': 'system'
        }
    
    @staticmethod
    def format_network_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format network device logs"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('level', 'INFO'),
            'device': raw_log.get('device'),
            'interface': raw_log.get('interface'),
            'src_ip': raw_log.get('src_ip'),
            'dst_ip': raw_log.get('dst_ip'),
            'protocol': raw_log.get('protocol'),
            'source_type': 'network'
        }
    
    @staticmethod
    def format_application_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format application logs"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('level', 'INFO'),
            'application': raw_log.get('app_name'),
            'module': raw_log.get('module'),
            'function': raw_log.get('function'),
            'line': raw_log.get('line'),
            'source_type': 'application'
        }
    
    @staticmethod
    def format_security_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format security/audit logs"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('severity', 'INFO'),
            'event_type': raw_log.get('event_type'),
            'user': raw_log.get('user'),
            'src_ip': raw_log.get('src_ip'),
            'action': raw_log.get('action'),
            'result': raw_log.get('result'),
            'source_type': 'security'
        }
    
    @staticmethod
    def format_web_server_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format web server logs (Apache/Nginx)"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': 'INFO',
            'client_ip': raw_log.get('client_ip'),
            'method': raw_log.get('method'),
            'path': raw_log.get('path'),
            'status_code': raw_log.get('status_code'),
            'response_time': raw_log.get('response_time'),
            'user_agent': raw_log.get('user_agent'),
            'source_type': 'web_server'
        }
    
    @staticmethod
    def format_container_log(raw_log: Dict[str, Any]) -> Dict[str, Any]:
        """Format container logs (Docker/Kubernetes)"""
        return {
            'content': raw_log.get('message', ''),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('level', 'INFO'),
            'container_id': raw_log.get('container_id'),
            'container_name': raw_log.get('container_name'),
            'pod_name': raw_log.get('pod_name'),
            'namespace': raw_log.get('namespace'),
            'source_type': 'container'
        }
    
    @staticmethod
    def format_log(raw_log: Dict[str, Any], source_type: LogSourceType) -> Dict[str, Any]:
        """Format log based on source type"""
        formatters = {
            LogSourceType.SYSTEM: LogFormatter.format_system_log,
            LogSourceType.NETWORK: LogFormatter.format_network_log,
            LogSourceType.APPLICATION: LogFormatter.format_application_log,
            LogSourceType.SECURITY: LogFormatter.format_security_log,
            LogSourceType.WEB_SERVER: LogFormatter.format_web_server_log,
            LogSourceType.CONTAINER: LogFormatter.format_container_log,
        }
        
        formatter = formatters.get(source_type)
        if formatter:
            return formatter(raw_log)
        
        # Default formatting
        return {
            'content': raw_log.get('message', str(raw_log)),
            'timestamp': raw_log.get('timestamp', datetime.now().isoformat()),
            'severity': raw_log.get('level', 'INFO'),
            'source_type': source_type.value
        }
