from typing import Dict, Any, Optional, List
import json
import requests
from dataclasses import dataclass

from src.utils.logger import get_logger
from src.utils.config_loader import config

logger = get_logger(__name__)

@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
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

class LLMEngine:
    def __init__(self):
        self.provider = config.get('llm.provider', 'ollama')
        self.model = config.get('llm.model', 'mistral:7b-instruct')
        self.temperature = config.get('llm.temperature', 0.1)
        self.max_tokens = config.get('llm.max_tokens', 2048)
        self.timeout = config.get('llm.timeout', 120)
        self.base_url = config.get('llm.base_url', 'http://localhost:11434')
        
        logger.info(f"LLMEngine initialized with {self.provider} - {self.model}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        if self.provider == 'ollama':
            return self._generate_ollama(prompt, system_prompt, **kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _generate_ollama(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get('temperature', self.temperature),
                "num_predict": kwargs.get('max_tokens', self.max_tokens),
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            
            return LLMResponse(
                content=result.get('response', ''),
                model=self.model,
                prompt_tokens=result.get('prompt_eval_count', 0),
                completion_tokens=result.get('eval_count', 0),
                total_tokens=result.get('prompt_eval_count', 0) + result.get('eval_count', 0)
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            return LLMResponse(
                content=f"Error: Unable to generate response - {str(e)}",
                model=self.model
            )
    
    def analyze_log_anomaly(self, log_content: str, context: str, template: str) -> LLMResponse:
        system_prompt = """You are an expert system administrator and log analysis specialist. 
Your task is to analyze log entries and identify potential issues, their root causes, and provide actionable recommendations.
Be concise, technical, and focus on actionable insights."""
        
        prompt = f"""Analyze the following log entry for anomalies or issues:

Log Entry:
{log_content}

Log Template:
{template}

Retrieved Knowledge Context:
{context}

Please provide:
1. Issue Identification: What is the problem?
2. Severity Assessment: How critical is this issue? (CRITICAL/HIGH/MEDIUM/LOW)
3. Root Cause Analysis: What likely caused this issue?
4. Impact Assessment: What systems or services are affected?
5. Recommended Actions: What steps should be taken to resolve this?

Provide your analysis in a structured format."""
        
        return self.generate(prompt, system_prompt)
    
    def generate_alert_explanation(self, log_content: str, severity: str, context: str) -> LLMResponse:
        system_prompt = """You are an expert at creating clear, actionable alerts for system administrators.
Generate concise but informative alert messages that help operators quickly understand and respond to issues."""
        
        prompt = f"""Generate a clear alert message for the following log anomaly:

Log Content:
{log_content}

Detected Severity: {severity}

Context from Knowledge Base:
{context}

Create an alert message that includes:
1. A brief summary of the issue (1-2 sentences)
2. The likely impact
3. Immediate recommended actions

Keep the message concise and actionable."""
        
        return self.generate(prompt, system_prompt)
    
    def extract_structured_info(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = "You are a data extraction specialist. Extract information from text according to the provided schema and return valid JSON."
        
        prompt = f"""Extract information from the following text according to this schema:

Schema:
{json.dumps(schema, indent=2)}

Text:
{text}

Return ONLY a valid JSON object matching the schema. Do not include any explanation."""
        
        response = self.generate(prompt, system_prompt, temperature=0.0)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response")
            return {}
    
    def check_health(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def list_models(self) -> List[str]:
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
