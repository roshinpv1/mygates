"""
LLM Analyzer - Intelligent code analysis using Large Language Models
Enhanced with enterprise support and token management
"""

import json
import re
import os
import uuid
import requests
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from ..models import Language, FileAnalysis
from ..utils.env_loader import EnvironmentLoader


# Ensure environment is loaded when module is imported
EnvironmentLoader.load_environment()


class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    LOCAL = "local"
    ENTERPRISE = "enterprise"


@dataclass
class LLMConfig:
    """LLM configuration"""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 8000


@dataclass
class TokenInfo:
    """Token information with expiry tracking"""
    token: str
    expires_at: datetime
    refresh_token: Optional[str] = None


@dataclass
class CodeAnalysisResult:
    """Result of LLM code analysis"""
    quality_score: float
    patterns_found: List[str]
    security_issues: List[str]
    recommendations: List[str]
    technology_insights: Dict[str, Any]
    code_smells: List[str]
    best_practices: List[str]


class EnterpriseTokenManager:
    """Manages enterprise LLM tokens with automatic refresh"""
    
    def __init__(self):
        self.token_info: Optional[TokenInfo] = None
        self.refresh_url = os.getenv("ENTERPRISE_LLM_REFRESH_URL")
        self.client_id = os.getenv("ENTERPRISE_LLM_CLIENT_ID")
        self.client_secret = os.getenv("ENTERPRISE_LLM_CLIENT_SECRET")
        self.refresh_token = os.getenv("ENTERPRISE_LLM_REFRESH_TOKEN")
        self.token_lock = threading.Lock()
        
        # Load initial token if provided
        initial_token = os.getenv("ENTERPRISE_LLM_TOKEN")
        if initial_token:
            # Default to 24 hours expiry if not specified
            expires_in_hours = int(os.getenv("ENTERPRISE_LLM_TOKEN_EXPIRY_HOURS", "24"))
            expires_at = datetime.now() + timedelta(hours=expires_in_hours)
            self.token_info = TokenInfo(
                token=initial_token,
                expires_at=expires_at,
                refresh_token=self.refresh_token
            )
    
    def get_valid_token(self) -> str:
        """Get a valid token, refreshing if necessary"""
        with self.token_lock:
            if not self.token_info:
                raise ValueError("No enterprise token configured. Set ENTERPRISE_LLM_TOKEN in .env file")
            
            # Check if token is expired or will expire in the next 5 minutes
            if datetime.now() >= (self.token_info.expires_at - timedelta(minutes=5)):
                print("🔄 Enterprise token expired or expiring soon, refreshing...")
                self._refresh_token()
            
            return self.token_info.token
    
    def _refresh_token(self):
        """Refresh the enterprise token"""
        if not self.refresh_url:
            raise ValueError("No refresh URL configured. Set ENTERPRISE_LLM_REFRESH_URL in .env file")
        
        if not self.refresh_token and not (self.client_id and self.client_secret):
            raise ValueError("No refresh credentials configured. Set either ENTERPRISE_LLM_REFRESH_TOKEN or both ENTERPRISE_LLM_CLIENT_ID and ENTERPRISE_LLM_CLIENT_SECRET in .env file")
        
        try:
            # Prepare refresh request
            headers = {"Content-Type": "application/json"}
            
            if self.refresh_token:
                # Use refresh token flow
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                }
            else:
                # Use client credentials flow
                data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            
            # Add any additional refresh headers from .env
            refresh_headers_str = os.getenv("ENTERPRISE_LLM_REFRESH_HEADERS", "{}")
            try:
                additional_headers = json.loads(refresh_headers_str)
                headers.update(additional_headers)
            except json.JSONDecodeError:
                print("⚠️ Warning: Invalid ENTERPRISE_LLM_REFRESH_HEADERS format, ignoring")
            
            # Configure proxy if specified
            proxies = self._get_proxy_config()
            
            print(f"🔄 Refreshing token from {self.refresh_url}")
            response = requests.post(
                self.refresh_url,
                headers=headers,
                json=data,
                proxies=proxies,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Token refresh failed with status {response.status_code}: {response.text}")
            
            token_data = response.json()
            
            # Extract new token and expiry
            new_token = token_data.get("access_token") or token_data.get("token")
            if not new_token:
                raise Exception(f"No access token in refresh response: {token_data}")
            
            # Calculate expiry time
            expires_in = token_data.get("expires_in", 24 * 3600)  # Default to 24 hours
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Update refresh token if provided
            new_refresh_token = token_data.get("refresh_token", self.refresh_token)
            
            # Update token info
            self.token_info = TokenInfo(
                token=new_token,
                expires_at=expires_at,
                refresh_token=new_refresh_token
            )
            
            print(f"✅ Token refreshed successfully, expires at {expires_at}")
            
        except Exception as e:
            print(f"❌ Token refresh failed: {str(e)}")
            raise Exception(f"Failed to refresh enterprise token: {str(e)}")

    def _get_proxy_config(self) -> Dict[str, str]:
        """Get proxy configuration from environment variables"""
        proxy = os.getenv("ENTERPRISE_LLM_PROXY")
        
        if proxy:
            # Use the same proxy for both HTTP and HTTPS
            return {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
        return {}


class LLMAnalyzer:
    """Enhanced LLM-powered code analyzer with enterprise support"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.enterprise_url = os.getenv("ENTERPRISE_LLM_URL")
        self.enterprise_model = os.getenv("ENTERPRISE_LLM_MODEL", "meta-llama-3.1-8b-instruct")
        self.enterprise_headers = self._parse_enterprise_headers()
        self.enterprise_api_key = os.getenv("ENTERPRISE_LLM_API_KEY")
        self.enterprise_use_case_id = os.getenv("ENTERPRISE_LLM_USE_CASE_ID")
        self.token_manager = EnterpriseTokenManager() if self.enterprise_url else None
        self.client = self._initialize_client()
        self.manager = None  # Will be set by LLMIntegrationManager for error verification

    def _parse_enterprise_headers(self) -> Dict[str, str]:
        """Parse enterprise LLM headers from environment variable."""
        headers_str = os.getenv("ENTERPRISE_LLM_HEADERS", "{}")
        try:
            return json.loads(headers_str)
        except json.JSONDecodeError:
            print("⚠️ Warning: Invalid ENTERPRISE_LLM_HEADERS format, using empty headers")
            return {}
    
    def _initialize_client(self):
        """Initialize LLM client based on provider"""
        
        # Check for enterprise configuration first
        if self.enterprise_url and self.token_manager and self.token_manager.token_info:
            print(f"✅ Using enterprise LLM at {self.enterprise_url}")
            return "enterprise"
        
        if self.config.provider == LLMProvider.OPENAI or self.config.provider == LLMProvider.LOCAL:
            try:
                import openai
                return openai.OpenAI(
                    api_key=self.config.api_key or "dummy-key",
                    base_url=self.config.base_url
                )
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        elif self.config.provider == LLMProvider.ANTHROPIC:
            try:
                import anthropic
                return anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        elif self.config.provider == LLMProvider.GEMINI:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.config.api_key)
                return genai.GenerativeModel(self.config.model)
            except ImportError:
                raise ImportError("Google AI library not installed. Run: pip install google-generativeai")
        
        elif self.config.provider == LLMProvider.OLLAMA:
            try:
                import ollama
                return ollama.Client(host=self.config.base_url or 'http://localhost:11434')
            except ImportError:
                raise ImportError("Ollama library not installed. Run: pip install ollama")
        
        else:
            return None  # Mock implementation

    def _prepare_enterprise_headers(self) -> Dict[str, str]:
        """Prepare headers for enterprise API request with dynamic values"""
        # Get valid token (will refresh if needed)
        token = self.token_manager.get_valid_token()
        
        # Generate current timestamp in required format
        current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # Base headers with dynamic values
        headers = {
            "Content-Type": "application/json",
            "X-REQUEST-ID": str(uuid.uuid4()),
            "X-XY-SESSION-ID": str(uuid.uuid4()),
            "X-CORRELATION-ID": str(uuid.uuid4()),
            "X-XY-CLIENT-ID": os.getenv("ENTERPRISE_LLM_CLIENT_ID", "MLOPS"),
            "X-XY-REQUEST-DATE": current_timestamp,
            "X-XY-CMP-ID": current_timestamp,
            "X-XY-TACHYON-API-KEY": "test",
            "Authorization": f"Bearer {token}"
        }
        
        # Add API key if provided
        if self.enterprise_api_key:
            headers["X-XY-API-KEY"] = self.enterprise_api_key
            
        # Add use case ID if provided
        if self.enterprise_use_case_id:
            headers["X-XY-USECASE-ID"] = self.enterprise_use_case_id
            
        # Add additional headers from configuration
        headers.update(self.enterprise_headers)
        
        return headers

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM with enhanced enterprise support"""
        
        # Check prompt size and warn if too large
        prompt_size = len(prompt)
        if prompt_size > 20000:  # ~5000 tokens
            print(f"⚠️ Warning: Large prompt size ({prompt_size} chars). May exceed context limits.")
        
        try:
            # Use enterprise LLM if configured
            if self.client == "enterprise":
                return self._make_enterprise_request(prompt)
            
            # Use standard providers
            if self.config.provider == LLMProvider.OPENAI or self.config.provider == LLMProvider.LOCAL:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": "You are a code analysis expert. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                return response.choices[0].message.content
            
            elif self.config.provider == LLMProvider.ANTHROPIC:
                response = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            elif self.config.provider == LLMProvider.GEMINI:
                response = self.client.generate_content(
                    prompt,
                    generation_config={
                        'temperature': self.config.temperature,
                        'max_output_tokens': self.config.max_tokens
                    }
                )
                return response.text
            
            elif self.config.provider == LLMProvider.OLLAMA:
                response = self.client.chat(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": "You are a code analysis expert. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    options={
                        'temperature': self.config.temperature,
                        'num_predict': self.config.max_tokens
                    }
                )
                return response['message']['content']
            
            else:
                raise ValueError(f"Unsupported LLM provider: {self.config.provider}")
                
        except Exception as e:
            error_msg = str(e)
            
            # Check if this might be a model availability issue
            model_error_keywords = ['model', 'not found', 'does not exist', 'unknown model', 'invalid model']
            if any(keyword in error_msg.lower() for keyword in model_error_keywords):
                print(f"🚨 Possible model availability issue detected")
                # Try to verify model availability
                if hasattr(self, 'manager') and hasattr(self.manager, 'verify_model_availability_on_error'):
                    self.manager.verify_model_availability_on_error(error_msg)
                else:
                    # Direct verification if no manager reference
                    self._verify_model_on_error(error_msg)
                    
                raise ValueError(f"Model availability issue: {error_msg}")
            
            # Handle specific context length errors
            elif any(keyword in error_msg.lower() for keyword in ['context', 'token', 'length', 'overflow']):
                print(f"❌ Context length error: {error_msg}")
                raise ValueError(f"Context too large for LLM: {error_msg}")
            
            # Handle timeout errors
            elif 'timeout' in error_msg.lower():
                print(f"❌ LLM request timeout: {error_msg}")
                raise ValueError(f"LLM request timeout: {error_msg}")
            
            # Handle other errors
            else:
                print(f"❌ LLM request failed: {error_msg}")
                raise Exception(f"LLM analysis failed: {error_msg}")
    
    def _verify_model_on_error(self, error_message: str):
        """Verify model availability when an LLM call fails (fallback method)"""
        if self.config.provider != LLMProvider.LOCAL:
            return
        
        try:
            import requests
            response = requests.get(f"{self.config.base_url.rstrip('/')}/models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                if isinstance(models, dict) and 'data' in models:
                    available_models = [model.get('id', '') for model in models['data']]
                    if self.config.model not in available_models:
                        print(f"❌ Confirmed: Model {self.config.model} not available")
                        print(f"   Available models: {available_models}")
        except Exception:
            pass  # Ignore verification errors

    def _make_enterprise_request(self, prompt: str) -> str:
        """Make request to enterprise LLM endpoint with token management."""
        try:
            # Prepare headers with dynamic values
            headers = self._prepare_enterprise_headers()
            
            # Prepare request data
            data = {
                "model": self.enterprise_model,
                "messages": [
                    {"role": "system", "content": "You are a code analysis expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": int(os.getenv("ENTERPRISE_LLM_MAX_TOKENS", "8000")),
                "temperature": float(os.getenv("ENTERPRISE_LLM_TEMPERATURE", "0.1"))
            }
            
            # Add any additional parameters from .env
            additional_params_str = os.getenv("ENTERPRISE_LLM_PARAMS", "{}")
            try:
                additional_params = json.loads(additional_params_str)
                data.update(additional_params)
            except json.JSONDecodeError:
                print("⚠️ Warning: Invalid ENTERPRISE_LLM_PARAMS format, ignoring")
            
            # Configure proxy if specified
            proxies = self.token_manager._get_proxy_config()
            
            print(f"🚀 Making enterprise LLM request to {self.enterprise_url}")
            print(f"   Model: {self.enterprise_model}")
            print(f"   Prompt size: {len(prompt)} characters")
            if proxies:
                print(f"   Using proxy: {proxies}")
            
            response = requests.post(
                self.enterprise_url,
                headers=headers,
                json=data,
                proxies=proxies,
                timeout=int(os.getenv("ENTERPRISE_LLM_TIMEOUT", "60"))
            )
            
            if response.status_code == 401:
                # Token might be invalid, try refreshing once
                print("🔄 Received 401, attempting token refresh...")
                headers = self._prepare_enterprise_headers()  # Refresh headers with new token
                
                response = requests.post(
                    self.enterprise_url,
                    headers=headers,
                    json=data,
                    proxies=proxies,
                    timeout=int(os.getenv("ENTERPRISE_LLM_TIMEOUT", "60"))
                )
            
            response.raise_for_status()
            response_data = response.json()
            
            # Extract content based on common enterprise API formats
            content = None
            if "choices" in response_data and response_data["choices"]:
                # OpenAI-compatible format
                content = response_data["choices"][0]["message"]["content"]
            elif "response" in response_data:
                # Simple response format
                content = response_data["response"]
            elif "content" in response_data:
                # Direct content format
                content = response_data["content"]
            elif "text" in response_data:
                # Text format
                content = response_data["text"]
            else:
                raise Exception(f"Unknown enterprise API response format: {list(response_data.keys())}")
            
            print(f"✅ Enterprise LLM response received: {len(content)} characters")
            return content
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Enterprise LLM API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Enterprise LLM request failed: {str(e)}")

    def analyze_gate_implementation(self, 
                                  gate_name: str,
                                  code_samples: List[str],
                                  language: Language,
                                  detected_technologies: Dict[str, List[str]]) -> CodeAnalysisResult:
        """Analyze gate implementation using LLM"""
        
        print(f"🤖 LLM analyzing {gate_name} with {len(code_samples)} code samples")
        
        # If no code samples, provide general recommendations for the gate
        if not code_samples:
            print(f"🤖 No code samples for {gate_name}, providing general recommendations")
            return self._provide_general_gate_recommendations(gate_name, language, detected_technologies)
        
        prompt = self._build_analysis_prompt(gate_name, code_samples, language, detected_technologies)
        
        try:
            print(f"🤖 Calling LLM for {gate_name} analysis...")
            response = self._call_llm(prompt)
            print(f"🤖 LLM response received for {gate_name}")
            return self._parse_analysis_response(response)
        except Exception as e:
            print(f"🚨 LLM call failed for {gate_name}: {str(e)}")
            # Fallback to rule-based analysis
            return self._fallback_analysis(gate_name, code_samples, language)
    
    def _build_analysis_prompt(self, 
                             gate_name: str,
                             code_samples: List[str],
                             language: Language,
                             detected_technologies: Dict[str, List[str]]) -> str:
        """Build analysis prompt for LLM"""
        
        tech_context = ""
        if detected_technologies:
            tech_list = []
            for category, techs in detected_technologies.items():
                tech_list.extend(techs)
            tech_context = f"Detected technologies: {', '.join(tech_list)}"
        
        prompt = f"""
You are an expert software architect and security analyst. Analyze the following {language.value} code for {gate_name} implementation.

{tech_context}

Code samples to analyze:
```{language.value}
{chr(10).join(code_samples[:5])}  # Show first 5 samples
```

Please provide a comprehensive analysis in JSON format with the following structure:
{{
    "quality_score": <float 0-100>,
    "patterns_found": [<list of patterns detected>],
    "security_issues": [<list of security concerns>],
    "recommendations": [<list of specific improvements>],
    "technology_insights": {{
        "framework_usage": "<assessment of framework usage>",
        "best_practices": "<adherence to best practices>",
        "architecture_patterns": [<list of patterns used>]
    }},
    "code_smells": [<list of code quality issues>],
    "best_practices": [<list of best practices to follow>]
}}

Focus on:
1. **{gate_name} Implementation Quality**: How well is this gate implemented?
2. **Security Implications**: Any security risks or vulnerabilities?
3. **Technology-Specific Best Practices**: Given the detected technologies
4. **Maintainability**: Code structure and readability
5. **Performance**: Potential performance implications
6. **Scalability**: How well will this scale?

Provide specific, actionable recommendations with code examples where helpful.
"""
        return prompt
    
    def _parse_analysis_response(self, response: str) -> CodeAnalysisResult:
        """Parse LLM response into structured result"""
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Try to parse the entire response as JSON
                data = json.loads(response)
            
            return CodeAnalysisResult(
                quality_score=data.get('quality_score', 50.0),
                patterns_found=data.get('patterns_found', []),
                security_issues=data.get('security_issues', []),
                recommendations=data.get('recommendations', []),
                technology_insights=data.get('technology_insights', {}),
                code_smells=data.get('code_smells', []),
                best_practices=data.get('best_practices', [])
            )
        
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback parsing
            return self._parse_text_response(response)
    
    def _parse_text_response(self, response: str) -> CodeAnalysisResult:
        """Parse text response when JSON parsing fails"""
        
        # Extract information using regex patterns
        quality_score = 50.0
        quality_match = re.search(r'quality[_\s]*score[:\s]*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
        if quality_match:
            quality_score = float(quality_match.group(1))
        
        # Extract recommendations
        recommendations = []
        rec_section = re.search(r'recommendations?[:\s]*(.*?)(?=\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
        if rec_section:
            rec_text = rec_section.group(1)
            recommendations = [line.strip('- ').strip() for line in rec_text.split('\n') if line.strip()]
        
        return CodeAnalysisResult(
            quality_score=quality_score,
            patterns_found=[],
            security_issues=[],
            recommendations=recommendations[:5],  # Limit to top 5
            technology_insights={},
            code_smells=[],
            best_practices=[]
        )
    
    def _fallback_analysis(self, gate_name: str, code_samples: List[str], language: Language) -> CodeAnalysisResult:
        """Fallback analysis when LLM is unavailable"""
        
        # Rule-based analysis
        quality_score = 60.0  # Base score
        recommendations = []
        patterns_found = []
        
        # Basic pattern detection
        for sample in code_samples:
            if 'logger' in sample.lower():
                patterns_found.append('Logging usage detected')
            if 'try' in sample.lower() and 'catch' in sample.lower():
                patterns_found.append('Exception handling found')
            if 'async' in sample.lower() or 'await' in sample.lower():
                patterns_found.append('Async pattern detected')
        
        # Basic recommendations based on gate
        if gate_name.lower() in ['structured_logs', 'logging']:
            recommendations = [
                "Consider using structured logging with JSON format",
                "Add correlation IDs to log messages",
                "Implement consistent log levels"
            ]
        elif gate_name.lower() in ['error', 'exception']:
            recommendations = [
                "Ensure all exceptions are properly caught and logged",
                "Add contextual information to error messages",
                "Implement proper error recovery mechanisms"
            ]
        
        return CodeAnalysisResult(
            quality_score=quality_score,
            patterns_found=patterns_found,
            security_issues=[],
            recommendations=recommendations,
            technology_insights={},
            code_smells=[],
            best_practices=[]
        )
    
    def _mock_llm_response(self) -> str:
        """Mock LLM response for testing"""
        return """
        {
            "quality_score": 75.0,
            "patterns_found": ["Structured logging detected", "Error handling present"],
            "security_issues": ["Potential sensitive data in logs"],
            "recommendations": [
                "Implement log sanitization to prevent sensitive data exposure",
                "Add correlation IDs for better traceability",
                "Use structured logging format consistently"
            ],
            "technology_insights": {
                "framework_usage": "Good use of logging framework",
                "best_practices": "Following some best practices",
                "architecture_patterns": ["Observer pattern for logging"]
            },
            "code_smells": ["Inconsistent error handling"],
            "best_practices": ["Use dependency injection for loggers", "Implement centralized error handling"]
        }
        """
    
    def enhance_recommendations(self, 
                              base_recommendations: List[str],
                              gate_name: str,
                              language: Language,
                              detected_technologies: Dict[str, List[str]]) -> List[str]:
        """Enhance basic recommendations with LLM insights"""
        
        if not self.client:
            return base_recommendations
        
        prompt = f"""
Given these basic recommendations for {gate_name} in {language.value}:
{chr(10).join(f"- {rec}" for rec in base_recommendations)}

Technologies detected: {detected_technologies}

Please enhance these recommendations with:
1. Specific code examples
2. Technology-specific best practices
3. Implementation steps
4. Potential pitfalls to avoid

Provide 3-5 enhanced, actionable recommendations in a simple list format.
"""
        
        try:
            response = self._call_llm(prompt)
            
            # Extract recommendations from response
            enhanced_recs = []
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('•') or line[0].isdigit()):
                    enhanced_recs.append(line.lstrip('-•0123456789. '))
            
            return enhanced_recs[:5] if enhanced_recs else base_recommendations
        
        except Exception:
            return base_recommendations
    
    def generate_code_examples(self, 
                             gate_name: str,
                             language: Language,
                             detected_technologies: Dict[str, List[str]]) -> List[str]:
        """Generate code examples for implementing the gate"""
        
        if not self.client:
            return []
        
        tech_context = ""
        if detected_technologies:
            main_techs = []
            for category, techs in detected_technologies.items():
                main_techs.extend(techs[:2])  # Top 2 from each category
            tech_context = f"using {', '.join(main_techs[:3])}"
        
        prompt = f"""
Generate 2-3 practical code examples for implementing {gate_name} in {language.value} {tech_context}.

Examples should be:
1. Production-ready
2. Following best practices
3. Technology-specific
4. Well-commented
5. Realistic (not toy examples)

Format each example with a brief description followed by the code.
"""
        
        try:
            response = self._call_llm(prompt)
            
            # Parse code examples from response
            examples = []
            code_blocks = re.findall(r'```[\w]*\n(.*?)\n```', response, re.DOTALL)
            for i, code in enumerate(code_blocks[:3]):
                examples.append(f"Example {i+1}:\n```{language.value}\n{code.strip()}\n```")
            
            return examples
        
        except Exception:
            return []
    
    def _provide_general_gate_recommendations(self, 
                                            gate_name: str,
                                            language: Language,
                                            detected_technologies: Dict[str, List[str]]) -> CodeAnalysisResult:
        """Provide general recommendations for a gate when no code samples are found"""
        
        # Build a prompt for general gate implementation guidance
        tech_context = ""
        if detected_technologies:
            tech_list = []
            for category, techs in detected_technologies.items():
                tech_list.extend(techs)
            tech_context = f"Technologies detected: {', '.join(tech_list)}"
        
        prompt = f"""
You are an expert software architect. Provide implementation guidance for {gate_name} in {language.value}.

{tech_context}

No existing implementation was found. Please provide:

1. **Why this gate is important** (security, reliability, maintainability)
2. **How to implement** {gate_name} in {language.value}
3. **Best practices** specific to the detected technologies
4. **Common pitfalls** to avoid
5. **Specific recommendations** with examples

Respond in JSON format:
{{
    "quality_score": 0,
    "patterns_found": [],
    "security_issues": ["Missing {gate_name} implementation"],
    "recommendations": [<5-7 specific implementation recommendations>],
    "technology_insights": {{
        "framework_usage": "<how to use detected frameworks>",
        "best_practices": "<technology-specific best practices>",
        "implementation_steps": [<step by step guide>]
    }},
    "code_smells": ["No {gate_name} implementation found"],
    "best_practices": [<list of best practices for this gate>]
}}
"""
        
        try:
            print(f"🤖 Getting general recommendations for {gate_name}...")
            response = self._call_llm(prompt)
            print(f"🤖 General recommendations received for {gate_name}")
            return self._parse_analysis_response(response)
        except Exception as e:
            print(f"🚨 Failed to get general recommendations for {gate_name}: {str(e)}")
            # Return basic fallback recommendations
            return self._fallback_analysis(gate_name, [], language)


class LLMIntegrationManager:
    """Manages LLM integration for the gate validation system"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._get_default_config()
        self.analyzer = LLMAnalyzer(self.config) if config else None
        self.enabled = config is not None
        
        # Pass manager reference to analyzer for error verification
        if self.analyzer:
            self.analyzer.manager = self
        
        # Cache for availability check
        self._availability_cache = None
        self._last_availability_check = None
        self._availability_cache_duration = 300  # 5 minutes in seconds
    
    def _get_default_config(self) -> LLMConfig:
        """Get default LLM configuration"""
        return LLMConfig(
            provider=LLMProvider.LOCAL,
            model="mock",
            temperature=0.1
        )
    
    def _should_check_availability(self) -> bool:
        """Check if we need to perform availability check"""
        if self._last_availability_check is None:
            return True
        
        from datetime import datetime, timedelta
        now = datetime.now()
        cache_expiry = self._last_availability_check + timedelta(seconds=self._availability_cache_duration)
        
        return now > cache_expiry
    
    def is_enabled(self) -> bool:
        """Check if LLM integration is properly enabled and accessible"""
        if not self.config:
            return False
        
        # Use cached result if available and not expired
        if not self._should_check_availability() and self._availability_cache is not None:
            return self._availability_cache
        
        # For cloud providers, just check if we have the required config (no HTTP call)
        if self.config.provider != LLMProvider.LOCAL:
            is_available = bool(self.config.api_key and self.config.model)
            self._availability_cache = is_available
            self._last_availability_check = datetime.now()
            return is_available
        
        # For local LLM, assume it's working unless we've had a recent failure
        # Only do the HTTP check if this is the first time or if cache expired
        if self._last_availability_check is None:
            # First time - do a quick check
            try:
                import requests
                from datetime import datetime
                
                response = requests.get(
                    f"{self.config.base_url.rstrip('/')}/models",
                    timeout=2  # Very quick timeout
                )
                
                if response.status_code == 200:
                    models = response.json()
                    print(f"🤖 LLM service available at: {self.config.base_url}")
                    
                    # Check if our model is available
                    if isinstance(models, dict) and 'data' in models:
                        available_models = [model.get('id', '') for model in models['data']]
                    else:
                        available_models = []
                    
                    is_available = self.config.model in available_models
                    
                    if is_available:
                        print(f"✅ Model {self.config.model} confirmed available")
                    else:
                        print(f"⚠️ Model {self.config.model} not found, but will try to use it anyway")
                        print(f"   Available models: {available_models}")
                        # Still return True - let the actual LLM call fail if model is wrong
                        is_available = True
                    
                    self._availability_cache = is_available
                    self._last_availability_check = datetime.now()
                    return is_available
                else:
                    print(f"⚠️ LLM service check failed with status {response.status_code}, assuming available")
                    # Assume it's working - let LLM calls handle the errors
                    self._availability_cache = True
                    self._last_availability_check = datetime.now()
                    return True
                    
            except Exception as e:
                print(f"⚠️ LLM service check failed: {e}, assuming available")
                # Assume it's working - let LLM calls handle the errors
                self._availability_cache = True
                self._last_availability_check = datetime.now()
                return True
        else:
            # Not first time and cache hasn't expired - assume it's working
            return self._availability_cache if self._availability_cache is not None else True
    
    def verify_model_availability_on_error(self, error_message: str) -> bool:
        """Verify model availability when an LLM call fails"""
        print(f"🔍 LLM call failed, verifying model availability...")
        print(f"   Error: {error_message}")
        
        if self.config.provider != LLMProvider.LOCAL:
            print("   Cloud provider - cannot verify model list")
            return False
        
        try:
            import requests
            from datetime import datetime
            
            response = requests.get(
                f"{self.config.base_url.rstrip('/')}/models",
                timeout=5
            )
            
            if response.status_code == 200:
                models = response.json()
                print(f"🤖 Checking available models at: {self.config.base_url}")
                
                if isinstance(models, dict) and 'data' in models:
                    available_models = [model.get('id', '') for model in models['data']]
                else:
                    available_models = []
                
                if self.config.model in available_models:
                    print(f"✅ Model {self.config.model} is available - error might be temporary")
                    return True
                else:
                    print(f"❌ Model {self.config.model} not found in LLM service")
                    print(f"   Available models: {available_models}")
                    print(f"   Please update your model name or load the correct model")
                    
                    # Update cache to reflect the issue
                    self._availability_cache = False
                    self._last_availability_check = datetime.now()
                    return False
            else:
                print(f"⚠️ LLM service returned status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️ Failed to verify model availability: {e}")
            return False
    
    def set_availability_cache_duration(self, seconds: int):
        """Set the duration for caching availability checks"""
        self._availability_cache_duration = seconds
    
    def get_availability_status(self) -> Dict[str, Any]:
        """Get detailed availability status including cache info"""
        from datetime import datetime, timedelta
        
        status = {
            'enabled': self.enabled,
            'cached_result': self._availability_cache,
            'cache_valid': False,
            'last_check': None,
            'next_check': None
        }
        
        if self._last_availability_check:
            status['last_check'] = self._last_availability_check.isoformat()
            cache_expiry = self._last_availability_check + timedelta(seconds=self._availability_cache_duration)
            status['cache_valid'] = datetime.now() < cache_expiry
            status['next_check'] = cache_expiry.isoformat()
        
        return status
    
    def force_availability_check(self) -> bool:
        """Force a fresh availability check, bypassing cache"""
        print("🔄 Forcing fresh LLM availability check...")
        self._last_availability_check = None
        self._availability_cache = None
        return self.is_enabled()
    
    def enhance_gate_validation(self, 
                              gate_name: str,
                              matches: List[Dict[str, Any]],
                              language: Language,
                              detected_technologies: Dict[str, List[str]],
                              base_recommendations: List[str]) -> Dict[str, Any]:
        """Enhance gate validation with LLM analysis"""
        
        if not self.is_enabled():
            return {
                'enhanced_quality_score': None,
                'llm_recommendations': base_recommendations,
                'code_examples': [],
                'security_insights': [],
                'technology_insights': {}
            }
        
        # Extract code samples from matches
        code_samples = [match.get('match', '') for match in matches[:10]]  # Limit to 10 samples
        
        # Perform LLM analysis
        analysis = self.analyzer.analyze_gate_implementation(
            gate_name, code_samples, language, detected_technologies
        )
        
        # Enhance recommendations
        enhanced_recommendations = self.analyzer.enhance_recommendations(
            base_recommendations, gate_name, language, detected_technologies
        )
        
        # Generate code examples
        code_examples = self.analyzer.generate_code_examples(
            gate_name, language, detected_technologies
        )
        
        return {
            'enhanced_quality_score': analysis.quality_score,
            'llm_recommendations': enhanced_recommendations,
            'code_examples': code_examples,
            'security_insights': analysis.security_issues,
            'technology_insights': analysis.technology_insights,
            'patterns_found': analysis.patterns_found,
            'code_smells': analysis.code_smells,
            'best_practices': analysis.best_practices
        } 