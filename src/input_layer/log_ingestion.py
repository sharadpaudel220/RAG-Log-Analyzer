import json
from pathlib import Path
from typing import List, Dict, Any, Generator, Optional
from dataclasses import dataclass
from datetime import datetime
import re

from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class RawLogEntry:
    content: str
    timestamp: Optional[datetime] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'source_file': self.source_file,
            'line_number': self.line_number,
            'metadata': self.metadata or {}
        }

class LogIngestion:
    def __init__(self):
        self.supported_formats = config.get('input.supported_formats', ['txt', 'log', 'json'])
        self.batch_size = config.get('input.batch_size', 1000)
        logger.info(f"LogIngestion initialized with formats: {self.supported_formats}")
    
    def ingest_file(self, file_path: str) -> List[RawLogEntry]:
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        file_extension = file_path.suffix.lstrip('.')
        
        if file_extension not in self.supported_formats:
            logger.warning(f"Unsupported format: {file_extension}, treating as text")
        
        logger.info(f"Ingesting log file: {file_path}")
        
        if file_extension == 'json':
            return self._ingest_json(file_path)
        else:
            return self._ingest_text(file_path)
    
    def _ingest_text(self, file_path: Path) -> List[RawLogEntry]:
        entries = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                timestamp = self._extract_timestamp(line)
                
                entry = RawLogEntry(
                    content=line,
                    timestamp=timestamp,
                    source_file=str(file_path),
                    line_number=line_num
                )
                entries.append(entry)
        
        logger.info(f"Ingested {len(entries)} log entries from {file_path}")
        return entries
    
    def _ingest_json(self, file_path: Path) -> List[RawLogEntry]:
        entries = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    log_data = json.loads(line.strip())
                    
                    content = log_data.get('message', log_data.get('msg', str(log_data)))
                    
                    timestamp = None
                    if 'timestamp' in log_data:
                        timestamp = self._parse_timestamp(log_data['timestamp'])
                    elif 'time' in log_data:
                        timestamp = self._parse_timestamp(log_data['time'])
                    
                    entry = RawLogEntry(
                        content=content,
                        timestamp=timestamp,
                        source_file=str(file_path),
                        line_number=line_num,
                        metadata=log_data
                    )
                    entries.append(entry)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON at line {line_num}, treating as text")
                    entry = RawLogEntry(
                        content=line.strip(),
                        source_file=str(file_path),
                        line_number=line_num
                    )
                    entries.append(entry)
        
        logger.info(f"Ingested {len(entries)} JSON log entries from {file_path}")
        return entries
    
    def ingest_batch(self, file_paths: List[str]) -> List[RawLogEntry]:
        all_entries = []
        
        for file_path in file_paths:
            try:
                entries = self.ingest_file(file_path)
                all_entries.extend(entries)
            except Exception as e:
                logger.error(f"Error ingesting {file_path}: {e}")
        
        return all_entries
    
    def stream_logs(self, file_path: str) -> Generator[RawLogEntry, None, None]:
        file_path = Path(file_path)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                timestamp = self._extract_timestamp(line)
                
                yield RawLogEntry(
                    content=line,
                    timestamp=timestamp,
                    source_file=str(file_path),
                    line_number=line_num
                )
    
    def _extract_timestamp(self, log_line: str) -> Optional[datetime]:
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}',
            r'\d{10,13}',
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, log_line)
            if match:
                return self._parse_timestamp(match.group())
        
        return None
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        try:
            timestamp_int = int(timestamp_str)
            if timestamp_int > 1e12:
                return datetime.fromtimestamp(timestamp_int / 1000)
            else:
                return datetime.fromtimestamp(timestamp_int)
        except (ValueError, OSError):
            pass
        
        return None
    
    def validate_logs(self, entries: List[RawLogEntry]) -> Dict[str, Any]:
        total = len(entries)
        with_timestamps = sum(1 for e in entries if e.timestamp is not None)
        
        avg_length = sum(len(e.content) for e in entries) / total if total > 0 else 0
        
        return {
            'total_entries': total,
            'entries_with_timestamps': with_timestamps,
            'timestamp_coverage': with_timestamps / total if total > 0 else 0,
            'average_content_length': avg_length
        }
