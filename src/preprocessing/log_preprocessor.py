import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from src.input_layer.log_ingestion import RawLogEntry
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class ParsedLogEntry:
    raw_content: str
    template: str
    template_id: int
    parameters: List[str]
    timestamp: Optional[datetime] = None
    severity: Optional[str] = None
    component: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'raw_content': self.raw_content,
            'template': self.template,
            'template_id': self.template_id,
            'parameters': self.parameters,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'severity': self.severity,
            'component': self.component,
            'source_file': self.source_file,
            'line_number': self.line_number,
            'metadata': self.metadata
        }

class LogPreprocessor:
    def __init__(self):
        self.config = config
        self._initialize_drain3()
        
        self.severity_patterns = {
            'CRITICAL': re.compile(r'\b(CRITICAL|FATAL|EMERGENCY)\b', re.IGNORECASE),
            'ERROR': re.compile(r'\b(ERROR|ERR|FAILURE|FAILED)\b', re.IGNORECASE),
            'WARNING': re.compile(r'\b(WARNING|WARN)\b', re.IGNORECASE),
            'INFO': re.compile(r'\b(INFO|INFORMATION)\b', re.IGNORECASE),
            'DEBUG': re.compile(r'\b(DEBUG|TRACE)\b', re.IGNORECASE),
        }
        
        self.component_pattern = re.compile(r'\[([^\]]+)\]|\(([^\)]+)\)|^(\w+):')
        
        logger.info("LogPreprocessor initialized with Drain3")
    
    def _initialize_drain3(self):
        drain_config = TemplateMinerConfig()
        drain_config.load({
            'drain': {
                'depth': self.config.get('preprocessing.drain3.depth', 4),
                'sim_th': self.config.get('preprocessing.drain3.similarity_threshold', 0.4),
                'max_children': self.config.get('preprocessing.drain3.max_children', 100),
                'max_clusters': 1024
            },
            'masking': [
                {
                    'regex_pattern': r'\d+\.\d+\.\d+\.\d+',
                    'mask_with': '<IP>'
                },
                {
                    'regex_pattern': r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
                    'mask_with': '<UUID>'
                },
                {
                    'regex_pattern': r'\b\d{10,13}\b',
                    'mask_with': '<TIMESTAMP>'
                },
                {
                    'regex_pattern': r'0x[0-9a-fA-F]+',
                    'mask_with': '<HEX>'
                },
                {
                    'regex_pattern': r'\b\d+\b',
                    'mask_with': '<NUM>'
                }
            ]
        })
        
        self.template_miner = TemplateMiner(config=drain_config)
    
    def preprocess(self, raw_entries: List[RawLogEntry]) -> List[ParsedLogEntry]:
        parsed_entries = []
        
        logger.info(f"Preprocessing {len(raw_entries)} log entries")
        
        for entry in raw_entries:
            try:
                parsed = self._parse_entry(entry)
                parsed_entries.append(parsed)
            except Exception as e:
                logger.error(f"Error parsing log entry: {e}")
                parsed_entries.append(self._create_fallback_entry(entry))
        
        logger.info(f"Successfully parsed {len(parsed_entries)} entries")
        return parsed_entries
    
    def _parse_entry(self, entry: RawLogEntry) -> ParsedLogEntry:
        result = self.template_miner.add_log_message(entry.content)
        
        template = result['template_mined']
        template_id = result['cluster_id']
        
        parameters = self._extract_parameters(entry.content, template)
        
        severity = self._extract_severity(entry.content)
        component = self._extract_component(entry.content)
        
        return ParsedLogEntry(
            raw_content=entry.content,
            template=template,
            template_id=template_id,
            parameters=parameters,
            timestamp=entry.timestamp,
            severity=severity,
            component=component,
            source_file=entry.source_file,
            line_number=entry.line_number,
            metadata=entry.metadata or {}
        )
    
    def _extract_parameters(self, content: str, template: str) -> List[str]:
        template_parts = template.split('<*>')
        
        if len(template_parts) == 1:
            return []
        
        parameters = []
        remaining = content
        
        for i, part in enumerate(template_parts[:-1]):
            if part:
                idx = remaining.find(part)
                if idx != -1:
                    remaining = remaining[idx + len(part):]
            
            next_part = template_parts[i + 1]
            if next_part:
                idx = remaining.find(next_part)
                if idx != -1:
                    param = remaining[:idx].strip()
                    parameters.append(param)
                    remaining = remaining[idx:]
            else:
                parameters.append(remaining.strip())
        
        return parameters
    
    def _extract_severity(self, content: str) -> Optional[str]:
        for severity, pattern in self.severity_patterns.items():
            if pattern.search(content):
                return severity
        return 'INFO'
    
    def _extract_component(self, content: str) -> Optional[str]:
        match = self.component_pattern.search(content)
        if match:
            for group in match.groups():
                if group:
                    return group
        return None
    
    def _create_fallback_entry(self, entry: RawLogEntry) -> ParsedLogEntry:
        return ParsedLogEntry(
            raw_content=entry.content,
            template=entry.content,
            template_id=-1,
            parameters=[],
            timestamp=entry.timestamp,
            severity=self._extract_severity(entry.content),
            component=self._extract_component(entry.content),
            source_file=entry.source_file,
            line_number=entry.line_number,
            metadata=entry.metadata or {}
        )
    
    def get_templates(self) -> Dict[int, str]:
        templates = {}
        for cluster in self.template_miner.drain.clusters:
            templates[cluster.cluster_id] = cluster.get_template()
        return templates
    
    def get_statistics(self) -> Dict[str, Any]:
        clusters = self.template_miner.drain.clusters
        return {
            'total_clusters': len(clusters),
            'templates': {c.cluster_id: c.get_template() for c in clusters}
        }
    
    def normalize_timestamp(self, entries: List[ParsedLogEntry]) -> List[ParsedLogEntry]:
        for entry in entries:
            if entry.timestamp:
                entry.metadata['normalized_timestamp'] = entry.timestamp.isoformat()
        return entries
    
    def create_sequences(self, entries: List[ParsedLogEntry], window_size: int = 10) -> List[List[ParsedLogEntry]]:
        sequences = []
        
        sorted_entries = sorted(entries, key=lambda x: x.timestamp if x.timestamp else datetime.min)
        
        for i in range(0, len(sorted_entries), window_size):
            sequence = sorted_entries[i:i + window_size]
            if sequence:
                sequences.append(sequence)
        
        logger.info(f"Created {len(sequences)} sequences with window size {window_size}")
        return sequences
