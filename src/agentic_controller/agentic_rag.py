from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import re

from src.preprocessing.log_preprocessor import ParsedLogEntry
from src.retrieval.retrieval_system import RetrievalSystem, RetrievalResult
from src.llm_engine.llm_interface import LLMEngine, LLMResponse
from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

class ActionType(Enum):
    RETRIEVE = "retrieve"
    ANALYZE = "analyze"
    REFLECT = "reflect"
    GENERATE_ALERT = "generate_alert"
    FINISH = "finish"

@dataclass
class ReasoningStep:
    step_number: int
    thought: str
    action: ActionType
    action_input: Dict[str, Any]
    observation: str
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_number': self.step_number,
            'thought': self.thought,
            'action': self.action.value,
            'action_input': self.action_input,
            'observation': self.observation,
            'confidence': self.confidence
        }

@dataclass
class AgenticAnalysisResult:
    log_entry: ParsedLogEntry
    is_anomaly: bool
    severity: str
    reasoning_chain: List[ReasoningStep]
    retrieved_documents: List[RetrievalResult]
    final_analysis: str
    confidence_score: float
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'log_entry': self.log_entry.to_dict(),
            'is_anomaly': self.is_anomaly,
            'severity': self.severity,
            'reasoning_chain': [step.to_dict() for step in self.reasoning_chain],
            'retrieved_documents': [doc.to_dict() for doc in self.retrieved_documents],
            'final_analysis': self.final_analysis,
            'confidence_score': self.confidence_score,
            'recommendations': self.recommendations
        }

class AgenticController:
    def __init__(self, retrieval_system: RetrievalSystem, llm_engine: LLMEngine, force_full_react: bool = False):
        self.retrieval_system = retrieval_system
        self.llm_engine = llm_engine
        
        self.max_reasoning_steps = config.get('agentic.max_reasoning_steps', 3)  # Reduced from 5 to 3 for better performance
        self.reasoning_strategy = config.get('agentic.reasoning_strategy', 'react')
        self.enable_self_reflection = config.get('agentic.enable_self_reflection', True)
        self.confidence_threshold = config.get('agentic.confidence_threshold', 0.75)

        # When force_full_react is True, disable most fallbacks but keep template_cache for performance
        self.force_full_react = force_full_react
        self.fast_mode = False if force_full_react else config.get('agentic.fast_mode', True)
        self.early_stop_on_low_severity = False if force_full_react else config.get('agentic.early_stop_on_low_severity', True)
        self.skip_info_logs = False if force_full_react else config.get('agentic.skip_info_logs', True)
        self.skip_warning_logs = False if force_full_react else config.get('agentic.skip_warning_logs', True)
        self.only_analyze_errors = False if force_full_react else config.get('agentic.only_analyze_errors', True)
        self.max_steps_fast = self.max_reasoning_steps if force_full_react else config.get('agentic.max_steps_fast', 1)
        self.enable_template_cache = True  # Keep template cache enabled for performance

        self.template_cache = {} if self.enable_template_cache else None

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
        self.compiled_ignore_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ignore_patterns]
        
        mode_str = "FULL REACT MODE" if force_full_react else f"fast_mode={self.fast_mode}"
        logger.info(f"AgenticController initialized with {self.reasoning_strategy} strategy ({mode_str})")

    def _should_ignore_log(self, log_entry: ParsedLogEntry) -> bool:
        """Check if log should be ignored as system/infrastructure noise"""
        log_content_lower = log_entry.raw_content.lower()

        for pattern in self.compiled_ignore_patterns:
            if pattern.search(log_content_lower):
                return True

        return False

    def analyze_log(self, log_entry: ParsedLogEntry) -> AgenticAnalysisResult:
        logger.debug(f"Starting agentic analysis for log: {log_entry.raw_content[:100]}")

        # Skip system/infrastructure logs
        if self._should_ignore_log(log_entry):
            return self._create_fast_result(log_entry, is_anomaly=False, severity='INFO')
        
        if self.skip_info_logs and log_entry.severity in ['INFO', 'DEBUG']:
            return self._create_fast_result(log_entry, is_anomaly=False, severity='INFO')
        
        if self.skip_warning_logs and log_entry.severity in ['WARNING', 'WARN', 'LOW']:
            return self._create_fast_result(log_entry, is_anomaly=False, severity='LOW')
        
        if self.only_analyze_errors and log_entry.severity not in ['ERROR', 'CRITICAL', 'FATAL', 'HIGH']:
            return self._create_fast_result(log_entry, is_anomaly=False, severity=log_entry.severity)
        
        if self.enable_template_cache and log_entry.template:
            cache_key = f"{log_entry.template}_{log_entry.severity}"
            if cache_key in self.template_cache:
                logger.debug(f"Using cached analysis for template: {log_entry.template[:50]}")
                return self._create_cached_result(log_entry, self.template_cache[cache_key])
        
        reasoning_chain = []
        retrieved_documents = []
        current_context = self._build_initial_context(log_entry)
        
        max_steps = self.max_steps_fast if self.fast_mode else self.max_reasoning_steps
        
        for step_num in range(1, max_steps + 1):
            step = self._execute_reasoning_step(
                step_num, 
                log_entry, 
                current_context, 
                reasoning_chain,
                retrieved_documents
            )
            
            reasoning_chain.append(step)
            
            if step.action == ActionType.FINISH:
                logger.debug(f"Analysis completed in {step_num} steps")
                break
            
            if self.early_stop_on_low_severity and step_num >= 1:
                if log_entry.severity in ['LOW', 'INFO'] and step.confidence > 0.6:
                    logger.debug(f"Early stopping for low-severity log at step {step_num}")
                    break
            
            current_context = self._update_context(current_context, step)
        
        final_analysis, severity, confidence = self._generate_final_analysis(
            log_entry, 
            reasoning_chain, 
            retrieved_documents
        )
        
        is_anomaly = self._determine_anomaly(severity, confidence)
        recommendations = self._extract_recommendations(final_analysis)
        
        result = AgenticAnalysisResult(
            log_entry=log_entry,
            is_anomaly=is_anomaly,
            severity=severity,
            reasoning_chain=reasoning_chain,
            retrieved_documents=retrieved_documents,
            final_analysis=final_analysis,
            confidence_score=confidence,
            recommendations=recommendations
        )
        
        if self.enable_template_cache and log_entry.template:
            cache_key = f"{log_entry.template}_{log_entry.severity}"
            self.template_cache[cache_key] = {
                'severity': severity,
                'is_anomaly': is_anomaly,
                'final_analysis': final_analysis,
                'confidence': confidence
            }
        
        return result
    
    def _execute_reasoning_step(
        self, 
        step_num: int, 
        log_entry: ParsedLogEntry,
        context: Dict[str, Any],
        reasoning_chain: List[ReasoningStep],
        retrieved_documents: List[RetrievalResult]
    ) -> ReasoningStep:
        thought = self._generate_thought(step_num, log_entry, context, reasoning_chain)
        
        action, action_input = self._decide_action(thought, step_num, context)
        
        observation = self._execute_action(action, action_input, log_entry, retrieved_documents)
        
        confidence = self._assess_confidence(observation, context)
        
        return ReasoningStep(
            step_number=step_num,
            thought=thought,
            action=action,
            action_input=action_input,
            observation=observation,
            confidence=confidence
        )
    
    def _generate_thought(
        self, 
        step_num: int, 
        log_entry: ParsedLogEntry,
        context: Dict[str, Any],
        reasoning_chain: List[ReasoningStep]
    ) -> str:
        if step_num == 1:
            return f"I need to analyze this log entry: '{log_entry.raw_content[:100]}...' with severity {log_entry.severity}. First, I should retrieve relevant knowledge."
        
        previous_step = reasoning_chain[-1] if reasoning_chain else None
        
        if previous_step and previous_step.action == ActionType.RETRIEVE:
            if "No relevant" in previous_step.observation:
                return "The retrieval didn't find relevant knowledge. I should analyze the log based on patterns and severity."
            else:
                return "I have retrieved relevant knowledge. Now I should analyze the log entry in context of this information."
        
        elif previous_step and previous_step.action == ActionType.ANALYZE:
            if previous_step.confidence < self.confidence_threshold:
                return "My analysis confidence is low. I should retrieve more specific knowledge or reflect on the findings."
            else:
                return "I have sufficient confidence in my analysis. I should generate the final alert."
        
        elif previous_step and previous_step.action == ActionType.REFLECT:
            return "After reflection, I should now generate the final alert with my findings."
        
        return "I should finalize my analysis and generate the alert."
    
    def _decide_action(
        self, 
        thought: str, 
        step_num: int, 
        context: Dict[str, Any]
    ) -> tuple[ActionType, Dict[str, Any]]:
        if step_num == 1:
            return ActionType.RETRIEVE, {
                'query': context['log_content'],
                'severity': context.get('severity', 'INFO')
            }
        
        if 'retrieve' in thought.lower() and step_num < self.max_reasoning_steps - 1:
            return ActionType.RETRIEVE, {
                'query': context['log_content'],
                'severity': context.get('severity', 'INFO')
            }
        
        if 'analyze' in thought.lower() and not context.get('analyzed', False):
            return ActionType.ANALYZE, {
                'log_content': context['log_content'],
                'retrieved_context': context.get('retrieved_context', '')
            }
        
        if 'reflect' in thought.lower() and self.enable_self_reflection:
            return ActionType.REFLECT, {
                'current_analysis': context.get('current_analysis', '')
            }
        
        return ActionType.FINISH, {}
    
    def _execute_action(
        self, 
        action: ActionType, 
        action_input: Dict[str, Any],
        log_entry: ParsedLogEntry,
        retrieved_documents: List[RetrievalResult]
    ) -> str:
        if action == ActionType.RETRIEVE:
            results = self.retrieval_system.retrieve(
                query=action_input['query'],
                context={'severity': action_input.get('severity')}
            )
            
            retrieved_documents.extend(results)
            
            if results:
                context_text = self.retrieval_system.format_context(results)
                return f"Retrieved {len(results)} relevant documents:\n{context_text[:500]}..."
            else:
                return "No relevant documents found in knowledge base."
        
        elif action == ActionType.ANALYZE:
            response = self.llm_engine.analyze_log_anomaly(
                log_content=action_input['log_content'],
                context=action_input['retrieved_context'],
                template=log_entry.template
            )
            return response.content
        
        elif action == ActionType.REFLECT:
            reflection_prompt = f"Reflect on this analysis and assess its completeness:\n{action_input['current_analysis']}"
            response = self.llm_engine.generate(reflection_prompt)
            return response.content
        
        elif action == ActionType.FINISH:
            return "Analysis complete."
        
        return "Unknown action."
    
    def _assess_confidence(self, observation: str, context: Dict[str, Any]) -> float:
        confidence_indicators = {
            'high': ['clear', 'definitely', 'certain', 'confirmed', 'obvious'],
            'medium': ['likely', 'probably', 'suggests', 'indicates'],
            'low': ['unclear', 'uncertain', 'possibly', 'might', 'could']
        }
        
        observation_lower = observation.lower()
        
        high_count = sum(1 for word in confidence_indicators['high'] if word in observation_lower)
        medium_count = sum(1 for word in confidence_indicators['medium'] if word in observation_lower)
        low_count = sum(1 for word in confidence_indicators['low'] if word in observation_lower)
        
        if high_count > low_count:
            return 0.9
        elif medium_count > low_count:
            return 0.7
        elif low_count > 0:
            return 0.5
        else:
            return 0.6
    
    def _build_initial_context(self, log_entry: ParsedLogEntry) -> Dict[str, Any]:
        return {
            'log_content': log_entry.raw_content,
            'template': log_entry.template,
            'severity': log_entry.severity,
            'component': log_entry.component,
            'timestamp': log_entry.timestamp.isoformat() if log_entry.timestamp else None,
            'analyzed': False,
            'retrieved_context': ''
        }
    
    def _update_context(self, context: Dict[str, Any], step: ReasoningStep) -> Dict[str, Any]:
        if step.action == ActionType.RETRIEVE:
            context['retrieved_context'] = step.observation
        elif step.action == ActionType.ANALYZE:
            context['current_analysis'] = step.observation
            context['analyzed'] = True
        
        return context
    
    def _generate_final_analysis(
        self, 
        log_entry: ParsedLogEntry,
        reasoning_chain: List[ReasoningStep],
        retrieved_documents: List[RetrievalResult]
    ) -> tuple[str, str, float]:
        analysis_steps = [step.observation for step in reasoning_chain if step.action == ActionType.ANALYZE]
        
        if analysis_steps:
            final_analysis = analysis_steps[-1]
        else:
            context = self.retrieval_system.format_context(retrieved_documents)
            response = self.llm_engine.analyze_log_anomaly(
                log_content=log_entry.raw_content,
                context=context,
                template=log_entry.template
            )
            final_analysis = response.content
        
        severity = self._extract_severity(final_analysis, log_entry.severity)
        
        avg_confidence = sum(step.confidence for step in reasoning_chain) / len(reasoning_chain) if reasoning_chain else 0.5
        
        return final_analysis, severity, avg_confidence
    
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
        
        # Default to LOW severity when unclear - assume normal unless evidence suggests otherwise
        return default_severity or 'LOW'
    
    def _determine_anomaly(self, severity: str, confidence: float) -> bool:
        """Conservative anomaly detection - balance precision and recall.
        
        Key insight: We want good precision but not zero recall.
        INFO/LOW severity logs should almost never be anomalies regardless of confidence.
        MEDIUM/HIGH/CRITICAL use moderate confidence thresholds.
        """
        # Balanced thresholds - flag anomalies when there's reasonable evidence
        if severity == 'INFO':
            return False  # INFO logs are never anomalies
        elif severity == 'LOW':
            return False  # LOW severity logs are never anomalies  
        elif severity == 'MEDIUM':
            return confidence >= 0.6  # Moderate confidence for MEDIUM
        elif severity == 'HIGH':
            return confidence >= 0.5  # Lower threshold for HIGH severity
        elif severity == 'CRITICAL':
            return confidence >= 0.3  # Flag CRITICAL unless very low confidence
        else:
            return confidence >= 0.7  # Unknown severity - moderate confidence
    
    def _extract_recommendations(self, analysis: str) -> List[str]:
        recommendations = []
        
        lines = analysis.split('\n')
        in_recommendations = False
        
        for line in lines:
            line = line.strip()
            if 'recommend' in line.lower() or 'action' in line.lower():
                in_recommendations = True
                continue
            
            if in_recommendations and line:
                if line[0].isdigit() or line.startswith('-') or line.startswith('•'):
                    recommendations.append(line.lstrip('0123456789.-•) ').strip())
        
        return recommendations[:5]
    
    def _create_fast_result(self, log_entry: ParsedLogEntry, is_anomaly: bool, severity: str) -> AgenticAnalysisResult:
        return AgenticAnalysisResult(
            log_entry=log_entry,
            is_anomaly=is_anomaly,
            severity=severity,
            reasoning_chain=[],
            retrieved_documents=[],
            final_analysis=f"Low-severity log ({severity}): No detailed analysis required.",
            confidence_score=0.9,
            recommendations=[]
        )
    
    def _create_cached_result(self, log_entry: ParsedLogEntry, cached: Dict[str, Any]) -> AgenticAnalysisResult:
        return AgenticAnalysisResult(
            log_entry=log_entry,
            is_anomaly=cached['is_anomaly'],
            severity=cached['severity'],
            reasoning_chain=[],
            retrieved_documents=[],
            final_analysis=cached['final_analysis'],
            confidence_score=cached['confidence'],
            recommendations=[]
        )
