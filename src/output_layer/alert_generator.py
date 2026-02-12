from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

from src.agentic_controller.agentic_rag import AgenticAnalysisResult
from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class Alert:
    alert_id: str
    timestamp: datetime
    severity: str
    title: str
    description: str
    affected_component: Optional[str]
    log_entry: ParsedLogEntry
    reasoning_chain: Optional[List[Dict[str, Any]]] = None
    source_attribution: Optional[List[Dict[str, Any]]] = None
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'affected_component': self.affected_component,
            'log_entry': self.log_entry.to_dict(),
            'reasoning_chain': self.reasoning_chain,
            'source_attribution': self.source_attribution,
            'recommendations': self.recommendations,
            'confidence_score': self.confidence_score,
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    def to_human_readable(self) -> str:
        lines = [
            f"{'='*80}",
            f"ALERT: {self.title}",
            f"{'='*80}",
            f"Alert ID: {self.alert_id}",
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Severity: {self.severity}",
            f"Confidence: {self.confidence_score:.2%}",
            f"",
            f"Description:",
            f"{self.description}",
            f"",
        ]
        
        if self.affected_component:
            lines.extend([
                f"Affected Component: {self.affected_component}",
                f""
            ])
        
        if self.recommendations:
            lines.extend([
                f"Recommended Actions:",
                *[f"  {i+1}. {rec}" for i, rec in enumerate(self.recommendations)],
                f""
            ])
        
        if self.reasoning_chain:
            lines.extend([
                f"Reasoning Chain:",
                *[f"  Step {step['step_number']}: {step['thought'][:100]}..." for step in self.reasoning_chain],
                f""
            ])
        
        lines.append(f"{'='*80}")
        
        return '\n'.join(lines)

class AlertGenerator:
    def __init__(self):
        self.severity_levels = config.get('alerts.severity_levels', 
            ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'])
        self.include_reasoning_chain = config.get('alerts.include_reasoning_chain', True)
        self.include_source_attribution = config.get('alerts.include_source_attribution', True)
        self.include_recommendations = config.get('alerts.include_recommendations', True)
        
        self.alert_counter = 0
        
        logger.info("AlertGenerator initialized")
    
    def generate_alert(self, analysis_result: AgenticAnalysisResult) -> Alert:
        self.alert_counter += 1
        alert_id = f"ALERT-{datetime.now().strftime('%Y%m%d')}-{self.alert_counter:05d}"
        
        title = self._generate_title(analysis_result)
        description = self._generate_description(analysis_result)
        
        reasoning_chain = None
        if self.include_reasoning_chain:
            reasoning_chain = [step.to_dict() for step in analysis_result.reasoning_chain]
        
        source_attribution = None
        if self.include_source_attribution:
            source_attribution = [
                {
                    'title': doc.document.title,
                    'type': doc.document.doc_type,
                    'relevance': doc.relevance_score
                }
                for doc in analysis_result.retrieved_documents[:3]
            ]
        
        recommendations = []
        if self.include_recommendations:
            recommendations = analysis_result.recommendations
        
        alert = Alert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            severity=analysis_result.severity,
            title=title,
            description=description,
            affected_component=analysis_result.log_entry.component,
            log_entry=analysis_result.log_entry,
            reasoning_chain=reasoning_chain,
            source_attribution=source_attribution,
            recommendations=recommendations,
            confidence_score=analysis_result.confidence_score,
            metadata={
                'template_id': analysis_result.log_entry.template_id,
                'original_severity': analysis_result.log_entry.severity
            }
        )
        
        logger.info(f"Generated alert {alert_id} with severity {alert.severity}")
        return alert
    
    def generate_alerts_batch(self, analysis_results: List[AgenticAnalysisResult]) -> List[Alert]:
        alerts = []
        
        for result in analysis_results:
            if result.is_anomaly:
                alert = self.generate_alert(result)
                alerts.append(alert)
        
        logger.info(f"Generated {len(alerts)} alerts from {len(analysis_results)} analyses")
        return alerts
    
    def _generate_title(self, analysis_result: AgenticAnalysisResult) -> str:
        severity = analysis_result.severity
        component = analysis_result.log_entry.component or "System"
        
        analysis_lower = analysis_result.final_analysis.lower()
        
        if 'memory' in analysis_lower or 'oom' in analysis_lower:
            return f"{severity}: Memory Issue Detected in {component}"
        elif 'connection' in analysis_lower or 'timeout' in analysis_lower:
            return f"{severity}: Connection Issue in {component}"
        elif 'disk' in analysis_lower or 'storage' in analysis_lower:
            return f"{severity}: Storage Issue in {component}"
        elif 'authentication' in analysis_lower or 'permission' in analysis_lower:
            return f"{severity}: Authentication/Permission Issue in {component}"
        elif 'error' in analysis_lower or 'exception' in analysis_lower:
            return f"{severity}: Error Detected in {component}"
        else:
            return f"{severity}: Anomaly Detected in {component}"
    
    def _generate_description(self, analysis_result: AgenticAnalysisResult) -> str:
        lines = []
        
        lines.append(f"Log Content: {analysis_result.log_entry.raw_content[:200]}")
        lines.append("")
        lines.append("Analysis:")
        
        analysis_lines = analysis_result.final_analysis.split('\n')
        for line in analysis_lines[:10]:
            if line.strip():
                lines.append(line.strip())
        
        return '\n'.join(lines)
    
    def save_alerts(self, alerts: List[Alert], output_path: str):
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'total_alerts': len(alerts),
            'alerts': [alert.to_dict() for alert in alerts]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Saved {len(alerts)} alerts to {output_path}")
    
    def filter_alerts(self, alerts: List[Alert], 
                     min_severity: Optional[str] = None,
                     min_confidence: Optional[float] = None) -> List[Alert]:
        filtered = alerts
        
        if min_severity:
            severity_order = {s: i for i, s in enumerate(self.severity_levels)}
            min_level = severity_order.get(min_severity, 0)
            
            filtered = [
                a for a in filtered 
                if severity_order.get(a.severity, 0) <= min_level
            ]
        
        if min_confidence:
            filtered = [a for a in filtered if a.confidence_score >= min_confidence]
        
        logger.info(f"Filtered {len(alerts)} alerts to {len(filtered)}")
        return filtered
    
    def get_statistics(self, alerts: List[Alert]) -> Dict[str, Any]:
        severity_counts = {}
        for alert in alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
        
        avg_confidence = sum(a.confidence_score for a in alerts) / len(alerts) if alerts else 0
        
        return {
            'total_alerts': len(alerts),
            'severity_distribution': severity_counts,
            'average_confidence': avg_confidence,
            'alerts_with_recommendations': sum(1 for a in alerts if a.recommendations)
        }
