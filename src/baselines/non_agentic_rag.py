from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.retrieval.retrieval_system import RetrievalSystem, RetrievalResult
from src.llm_engine.llm_interface import LLMEngine
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class NonAgenticRAGResult:
    log_entry: ParsedLogEntry
    is_anomaly: bool
    severity: str
    analysis: str
    retrieved_documents: List[RetrievalResult]
    confidence_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_entry': self.log_entry.to_dict(),
            'is_anomaly': self.is_anomaly,
            'severity': self.severity,
            'analysis': self.analysis,
            'retrieved_documents': [doc.to_dict() for doc in self.retrieved_documents],
            'confidence_score': self.confidence_score
        }

class NonAgenticRAGSystem:
    def __init__(self, retrieval_system: RetrievalSystem, llm_engine: LLMEngine):
        self.retrieval_system = retrieval_system
        self.llm_engine = llm_engine

        self.top_k = config.get('baselines.non_agentic_rag.top_k', 5)
        self.single_pass = config.get('baselines.non_agentic_rag.single_pass', True)

        # Ignore patterns for system/infrastructure logs
        self.ignore_patterns = [
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
            r'ingestion'
        ]
        self.compiled_ignore_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ignore_patterns]

        logger.info("NonAgenticRAGSystem initialized")

    def _should_ignore_log(self, log_entry: ParsedLogEntry) -> bool:
        """Check if log should be ignored as system/infrastructure noise"""
        log_content_lower = log_entry.raw_content.lower()

        for pattern in self.compiled_ignore_patterns:
            if pattern.search(log_content_lower):
                return True

        return False

    def analyze(self, log_entry: ParsedLogEntry) -> NonAgenticRAGResult:
        # Skip system/infrastructure logs
        if self._should_ignore_log(log_entry):
            return NonAgenticRAGResult(
                log_entry=log_entry,
                is_anomaly=False,
                severity='INFO',
                analysis='System infrastructure log - ignored',
                retrieved_documents=[],
                confidence_score=1.0
            )
        retrieved_docs = self.retrieval_system.retrieve(
            query=log_entry.raw_content,
            top_k=self.top_k,
            context={'severity': log_entry.severity}
        )
        
        context = self.retrieval_system.format_context(retrieved_docs)
        
        response = self.llm_engine.analyze_log_anomaly(
            log_content=log_entry.raw_content,
            context=context,
            template=log_entry.template
        )
        
        analysis = response.content
        
        severity = self._extract_severity(analysis, log_entry.severity)
        
        is_anomaly = self._determine_anomaly(severity, analysis)
        
        confidence_score = self._estimate_confidence(analysis, retrieved_docs)
        
        return NonAgenticRAGResult(
            log_entry=log_entry,
            is_anomaly=is_anomaly,
            severity=severity,
            analysis=analysis,
            retrieved_documents=retrieved_docs,
            confidence_score=confidence_score
        )
    
    def analyze_batch(self, log_entries: List[ParsedLogEntry]) -> List[NonAgenticRAGResult]:
        results = []
        
        for entry in log_entries:
            result = self.analyze(entry)
            results.append(result)
        
        anomaly_count = sum(1 for r in results if r.is_anomaly)
        logger.info(f"Non-Agentic RAG analysis: {anomaly_count}/{len(results)} anomalies detected")
        
        return results
    
    def _extract_severity(self, analysis: str, default_severity: str) -> str:
        severity_keywords = {
            'CRITICAL': ['critical', 'fatal', 'emergency', 'severe'],
            'HIGH': ['high', 'error', 'failure', 'failed'],
            'MEDIUM': ['medium', 'warning', 'warn'],
            'LOW': ['low', 'minor', 'info'],
        }
        
        analysis_lower = analysis.lower()
        
        for severity, keywords in severity_keywords.items():
            if any(keyword in analysis_lower for keyword in keywords):
                return severity
        
        return default_severity or 'MEDIUM'
    
    def _determine_anomaly(self, severity: str, analysis: str) -> bool:
        severity_scores = {
            'CRITICAL': 1.0,
            'HIGH': 0.8,
            'MEDIUM': 0.5,
            'LOW': 0.3,
            'INFO': 0.1
        }
        
        severity_score = severity_scores.get(severity, 0.5)
        
        anomaly_keywords = ['error', 'failure', 'exception', 'critical', 'issue', 'problem']
        keyword_score = sum(1 for keyword in anomaly_keywords if keyword in analysis.lower()) / len(anomaly_keywords)
        
        combined_score = (severity_score + keyword_score) / 2
        
        return combined_score >= 0.4
    
    def _estimate_confidence(self, analysis: str, retrieved_docs: List[RetrievalResult]) -> float:
        confidence_indicators = {
            'high': ['clear', 'definitely', 'certain', 'confirmed', 'obvious'],
            'low': ['unclear', 'uncertain', 'possibly', 'might', 'could']
        }
        
        analysis_lower = analysis.lower()
        
        high_count = sum(1 for word in confidence_indicators['high'] if word in analysis_lower)
        low_count = sum(1 for word in confidence_indicators['low'] if word in analysis_lower)
        
        text_confidence = 0.7 if high_count > low_count else 0.5 if high_count == low_count else 0.3
        
        retrieval_confidence = sum(doc.relevance_score for doc in retrieved_docs) / len(retrieved_docs) if retrieved_docs else 0.0
        
        return (text_confidence + retrieval_confidence) / 2
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            'top_k': self.top_k,
            'single_pass': self.single_pass
        }
