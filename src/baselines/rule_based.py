import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class RuleBasedResult:
    log_entry: ParsedLogEntry
    is_anomaly: bool
    severity: str
    matched_rules: List[str]
    confidence_score: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_entry': self.log_entry.to_dict(),
            'is_anomaly': self.is_anomaly,
            'severity': self.severity,
            'matched_rules': self.matched_rules,
            'confidence_score': self.confidence_score
        }

class RuleBasedSystem:
    def __init__(self):
        self.error_keywords = config.get('baselines.rule_based.error_keywords',
            ['ERROR', 'FATAL', 'CRITICAL', 'EXCEPTION', 'FAILED'])
        self.threshold = config.get('baselines.rule_based.threshold', 1)

        # Ignore patterns for system/infrastructure logs and normal hardware events
        self.ignore_patterns = [
            # System/infrastructure logs
            r'initializing',
            r'network capture',
            r'starting network',
            r'network capture started',
            r'network capture stopped',
            r'network capture status',
            r'system healthy',
            r'health check',
            r'status check',
            r'configuration loaded',
            r'initialized successfully',
            r'startup complete',
            r'ready to accept',
            r'listening on',
            r'server started',
            r'service started',
            r'api server',
            r'web server',
            r'application started',
            r'bootstrapping',
            r'loading configuration',
            r'database connected',
            r'connection established',
            r'cache initialized',
            r'memory manager',
            r'log analyzer',
            r'agentic controller',
            r'retrieval system',
            r'knowledge base',
            r'preprocessing',
            r'ingestion',
            # Normal hardware events (often incorrectly labeled as anomalies in BGL)
            r'INFO.*parity error corrected',  # "instruction cache parity error corrected" is normal
            r'INFO.*alignment exceptions',     # "double-hummer alignment exceptions" is normal
            r'INFO.*generating core\.\d+',   # Core dumps during normal operation
            r'INFO.*CE sym',                  # Correctable error symbols
            r'RAS KERNEL INFO',               # RAS (Reliability, Availability, Serviceability) kernel info
        ]

        self.rules = self._initialize_rules()

        # Compile ignore patterns
        self.compiled_ignore_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ignore_patterns]

        logger.info(f"RuleBasedSystem initialized with {len(self.rules)} rules and {len(self.ignore_patterns)} ignore patterns")
    
    def _initialize_rules(self) -> List[Dict[str, Any]]:
        rules = []
        
        for keyword in self.error_keywords:
            rules.append({
                'name': f'keyword_{keyword}',
                'pattern': re.compile(rf'\b{keyword}\b', re.IGNORECASE),
                'severity': self._keyword_to_severity(keyword),
                'description': f'Matches {keyword} keyword'
            })
        
        rules.extend([
            {
                'name': 'exception_pattern',
                'pattern': re.compile(r'Exception|Error|Traceback', re.IGNORECASE),
                'severity': 'HIGH',
                'description': 'Matches exception patterns'
            },
            {
                'name': 'connection_timeout',
                'pattern': re.compile(r'connection.*timeout|timeout.*connection', re.IGNORECASE),
                'severity': 'MEDIUM',
                'description': 'Matches connection timeout patterns'
            },
            {
                'name': 'out_of_memory',
                'pattern': re.compile(r'out of memory|OOM|memory.*exhausted', re.IGNORECASE),
                'severity': 'CRITICAL',
                'description': 'Matches out of memory patterns'
            },
            {
                'name': 'disk_full',
                'pattern': re.compile(r'no space left|disk.*full|quota exceeded', re.IGNORECASE),
                'severity': 'HIGH',
                'description': 'Matches disk space issues'
            },
            {
                'name': 'authentication_failure',
                'pattern': re.compile(r'authentication.*failed|access denied|permission denied', re.IGNORECASE),
                'severity': 'MEDIUM',
                'description': 'Matches authentication failures'
            },
            {
                'name': 'service_unavailable',
                'pattern': re.compile(r'service.*unavailable|503|backend.*down', re.IGNORECASE),
                'severity': 'HIGH',
                'description': 'Matches service unavailability'
            }
        ])
        
        return rules
    
    def _keyword_to_severity(self, keyword: str) -> str:
        severity_map = {
            'FATAL': 'CRITICAL',
            'CRITICAL': 'CRITICAL',
            'ERROR': 'HIGH',
            'EXCEPTION': 'HIGH',
            'FAILED': 'MEDIUM',
            'WARNING': 'MEDIUM',
            'WARN': 'LOW'
        }
        return severity_map.get(keyword.upper(), 'MEDIUM')
    
    def _is_higher_severity(self, sev1: str, sev2: str) -> bool:
        severity_order = {
            'CRITICAL': 0,
            'HIGH': 1,
            'MEDIUM': 2,
            'LOW': 3,
            'INFO': 4
        }
        
        return severity_order.get(sev1, 4) < severity_order.get(sev2, 4)

    def _should_ignore_log(self, log_entry: ParsedLogEntry) -> bool:
        """Check if log should be ignored as system/infrastructure noise"""
        log_content_lower = log_entry.raw_content.lower()

        for pattern in self.compiled_ignore_patterns:
            if pattern.search(log_content_lower):
                return True

        return False

    def analyze(self, log_entry: ParsedLogEntry) -> RuleBasedResult:
        # Skip system/infrastructure logs
        if self._should_ignore_log(log_entry):
            return RuleBasedResult(
                log_entry=log_entry,
                is_anomaly=False,
                severity='INFO',
                matched_rules=[],
                confidence_score=1.0
            )

        matched_rules = []
        max_severity = 'INFO'

        for rule in self.rules:
            if rule['pattern'].search(log_entry.raw_content):
                matched_rules.append(rule['name'])

                if self._is_higher_severity(rule['severity'], max_severity):
                    max_severity = rule['severity']

        is_anomaly = len(matched_rules) >= self.threshold

        if not is_anomaly and log_entry.severity in ['ERROR', 'CRITICAL', 'FATAL']:
            is_anomaly = True
            max_severity = log_entry.severity
            matched_rules.append('severity_based')

        return RuleBasedResult(
            log_entry=log_entry,
            is_anomaly=is_anomaly,
            severity=max_severity,
            matched_rules=matched_rules,
            confidence_score=1.0
        )
    
    def add_rule(self, name: str, pattern: str, severity: str, description: str = ""):
        self.rules.append({
            'name': name,
            'pattern': re.compile(pattern, re.IGNORECASE),
            'severity': severity,
            'description': description
        })
        logger.info(f"Added rule: {name}")
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            'total_rules': len(self.rules),
            'error_keywords': self.error_keywords,
            'threshold': self.threshold
        }
