from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class MockLLMResponse:
    content: str
    model: str = "mock-llm"
    prompt_tokens: int = 100
    completion_tokens: int = 200
    total_tokens: int = 300
    finish_reason: str = "stop"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'model': self.model,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'finish_reason': self.finish_reason
        }

class MockLLMEngine:
    """Mock LLM Engine for testing without Ollama"""
    
    def __init__(self):
        self.provider = "mock"
        self.model = "mock-llm"
        logger.info("MockLLMEngine initialized (Ollama not available)")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> MockLLMResponse:
        # Generate mock response based on prompt content
        if "analyze" in prompt.lower() or "anomaly" in prompt.lower():
            content = self._generate_analysis_response(prompt)
        elif "alert" in prompt.lower():
            content = self._generate_alert_response(prompt)
        else:
            content = self._generate_generic_response(prompt)
        
        return MockLLMResponse(content=content)
    
    def _generate_analysis_response(self, prompt: str) -> str:
        # Extract severity from prompt
        severity = "HIGH"
        if "error" in prompt.lower() or "exception" in prompt.lower():
            severity = "HIGH"
        elif "fatal" in prompt.lower() or "critical" in prompt.lower():
            severity = "CRITICAL"
        elif "warning" in prompt.lower() or "warn" in prompt.lower():
            severity = "MEDIUM"
        
        return f"""**Issue Identification:**
The log entry indicates a {severity.lower()} severity issue in the system. Based on the log content and retrieved knowledge, this appears to be a system anomaly requiring attention.

**Severity Assessment:** {severity}
The severity is classified as {severity} based on the error patterns and potential impact on system operations.

**Root Cause Analysis:**
The issue likely stems from one of the following:
1. Network connectivity problems between system components
2. Resource exhaustion (memory, disk, or connections)
3. Configuration issues or permission problems
4. Software bugs or unexpected system state

**Impact Assessment:**
This issue may affect:
- System availability and reliability
- Data processing capabilities
- User-facing services
- Dependent system components

**Recommended Actions:**
1. Investigate the immediate cause by checking system logs and metrics
2. Verify network connectivity and resource availability
3. Check configuration settings and permissions
4. Monitor for similar patterns in other components
5. Implement corrective measures based on findings
"""
    
    def _generate_alert_response(self, prompt: str) -> str:
        return """**Alert Summary:**
A system anomaly has been detected that requires immediate attention. The issue appears to be related to service availability or resource constraints.

**Impact:**
This may affect system performance and user experience. Immediate investigation is recommended.

**Immediate Actions:**
1. Check system health and resource utilization
2. Review recent changes or deployments
3. Verify service connectivity
4. Escalate if issue persists
"""
    
    def _generate_generic_response(self, prompt: str) -> str:
        return "Based on the provided information, the analysis suggests this is a notable event that warrants further investigation. Please review the context and take appropriate action."
    
    def analyze_log_anomaly(self, log_content: str, context: str, template: str) -> MockLLMResponse:
        prompt = f"Analyze log: {log_content}\nContext: {context}\nTemplate: {template}"
        return self.generate(prompt)
    
    def generate_alert_explanation(self, log_content: str, severity: str, context: str) -> MockLLMResponse:
        prompt = f"Generate alert for: {log_content}\nSeverity: {severity}\nContext: {context}"
        return self.generate(prompt)
    
    def extract_structured_info(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        return {}
    
    def check_health(self) -> bool:
        return True
    
    def list_models(self):
        return ["mock-llm"]
