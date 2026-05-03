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

        self.openai_api_key = config.get_env('OPENAI_API_KEY') or config.get('llm.openai.api_key', '')
        self.openai_base_url = config.get('llm.openai.base_url', 'https://api.openai.com')

        self.anthropic_api_key = config.get_env('ANTHROPIC_API_KEY') or config.get('llm.anthropic.api_key', '')
        self.anthropic_base_url = config.get('llm.anthropic.base_url', 'https://api.anthropic.com')
        self.anthropic_version = config.get('llm.anthropic.version', '2023-06-01')

        self.gemini_api_key = config.get_env('GEMINI_API_KEY') or config.get('llm.gemini.api_key', '')
        self.gemini_base_url = config.get('llm.gemini.base_url', 'https://generativelanguage.googleapis.com')

        self.groq_api_key = config.get_env('GROQ_API_KEY') or config.get('llm.groq.api_key', '')
        self.groq_base_url = config.get('llm.groq.base_url', 'https://api.groq.com/openai')

        logger.info(f"LLMEngine initialized with {self.provider} - {self.model}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        provider = (self.provider or '').lower().strip()
        provider_aliases = {
            'chatgpt': 'openai',
            'claude': 'anthropic',
            'google': 'gemini',
            'llama': 'groq',
            'groq-cloud': 'groq'
        }
        provider = provider_aliases.get(provider, provider)

        try:
            if provider == 'ollama':
                return self._generate_ollama(prompt, system_prompt, **kwargs)
            if provider == 'openai':
                return self._generate_openai(prompt, system_prompt, **kwargs)
            if provider == 'anthropic':
                return self._generate_anthropic(prompt, system_prompt, **kwargs)
            if provider == 'gemini':
                return self._generate_gemini(prompt, system_prompt, **kwargs)
            if provider == 'groq':
                return self._generate_groq(prompt, system_prompt, **kwargs)
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        except ValueError as e:
            logger.error(str(e))
            return LLMResponse(content=f"Error: {str(e)}", model=self.model)

    def _ensure_api_key(self, provider_name: str, api_key: str) -> None:
        if api_key:
            return
        env_var_name = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'gemini': 'GEMINI_API_KEY',
            'groq': 'GROQ_API_KEY'
        }.get(provider_name, 'API_KEY')
        raise ValueError(f"Missing API key for provider '{provider_name}'. Set {env_var_name} or configure llm.{provider_name}.api_key in config.yaml")
    
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

    def _generate_openai(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        self._ensure_api_key('openai', self.openai_api_key)
        url = f"{self.openai_base_url.rstrip('/')}/v1/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens)
        }

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            choice = (result.get('choices') or [{}])[0]
            message = choice.get('message') or {}
            content = message.get('content', '')

            usage = result.get('usage') or {}

            return LLMResponse(
                content=content,
                model=result.get('model', self.model),
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0),
                total_tokens=usage.get('total_tokens', 0),
                finish_reason=choice.get('finish_reason', 'stop')
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return LLMResponse(
                content=f"Error: Unable to generate response - {str(e)}",
                model=self.model
            )

    def _generate_anthropic(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        self._ensure_api_key('anthropic', self.anthropic_api_key)
        url = f"{self.anthropic_base_url.rstrip('/')}/v1/messages"

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "temperature": kwargs.get('temperature', self.temperature),
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            content_blocks = result.get('content') or []
            text_parts = []
            for block in content_blocks:
                if isinstance(block, dict) and block.get('type') == 'text':
                    text_parts.append(block.get('text', ''))
            content = "".join(text_parts)

            usage = result.get('usage') or {}

            return LLMResponse(
                content=content,
                model=result.get('model', self.model),
                prompt_tokens=usage.get('input_tokens', 0),
                completion_tokens=usage.get('output_tokens', 0),
                total_tokens=usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
                finish_reason=result.get('stop_reason', 'stop')
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return LLMResponse(
                content=f"Error: Unable to generate response - {str(e)}",
                model=self.model
            )

    def _generate_gemini(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        self._ensure_api_key('gemini', self.gemini_api_key)

        model_name = self.model
        if model_name.startswith('models/'):
            model_name = model_name[len('models/'):]
        url = f"{self.gemini_base_url.rstrip('/')}/v1beta/models/{model_name}:generateContent"

        user_text = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"

        payload: Dict[str, Any] = {
            "contents": [
                {"role": "user", "parts": [{"text": user_text}]}
            ],
            "generationConfig": {
                "temperature": kwargs.get('temperature', self.temperature),
                "maxOutputTokens": kwargs.get('max_tokens', self.max_tokens)
            }
        }

        try:
            response = requests.post(url, params={"key": self.gemini_api_key}, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            candidates = result.get('candidates') or []
            first = candidates[0] if candidates else {}
            content_obj = first.get('content') or {}
            parts = content_obj.get('parts') or []
            text_parts = []
            for part in parts:
                if isinstance(part, dict):
                    text_parts.append(part.get('text', ''))
            content = "".join(text_parts)

            return LLMResponse(
                content=content,
                model=self.model,
                finish_reason=first.get('finishReason', 'stop')
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Gemini API: {e}")
            return LLMResponse(
                content=f"Error: Unable to generate response - {str(e)}",
                model=self.model
            )
    
    def _generate_groq(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Groq Cloud — OpenAI-compatible API. Free tier: ~14,400 req/day.
        Recommended models: llama-3.1-8b-instant, llama-3.3-70b-versatile, mixtral-8x7b-32768."""
        self._ensure_api_key('groq', self.groq_api_key)
        url = f"{self.groq_base_url.rstrip('/')}/v1/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get('temperature', self.temperature),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens)
        }
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            choice = (result.get('choices') or [{}])[0]
            message = choice.get('message') or {}
            content = message.get('content', '')
            usage = result.get('usage') or {}

            return LLMResponse(
                content=content,
                model=result.get('model', self.model),
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0),
                total_tokens=usage.get('total_tokens', 0),
                finish_reason=choice.get('finish_reason', 'stop')
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Groq API: {e}")
            return LLMResponse(
                content=f"Error: Unable to generate response - {str(e)}",
                model=self.model
            )

    def analyze_log_anomaly(self, log_content: str, context: str, template: str) -> LLMResponse:
        system_prompt = "You are a log analysis expert. Analyze logs quickly and concisely."
        
        prompt = f"""Analyze this log for issues:

Log: {log_content}

Context: {context if context else 'None'}

Provide:
1. Issue (if any)
2. Severity (CRITICAL/HIGH/MEDIUM/LOW)
3. Root cause
4. Action needed

Be brief and technical."""
        
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
        provider = (self.provider or '').lower().strip()
        try:
            if provider == 'ollama':
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
                return response.status_code == 200
            if provider == 'groq':
                # An API key is sufficient evidence for cloud providers; a real
                # ping costs quota. Light validation only.
                return bool(self.groq_api_key)
            if provider in ('openai', 'chatgpt'):
                return bool(self.openai_api_key)
            if provider in ('anthropic', 'claude'):
                return bool(self.anthropic_api_key)
            if provider in ('gemini', 'google'):
                return bool(self.gemini_api_key)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def list_models(self) -> List[str]:
        try:
            if self.provider != 'ollama':
                return []
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
