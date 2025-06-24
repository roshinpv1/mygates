from fastapi import FastAPI, HTTPException, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import uvicorn
import json
import os
import re
import tempfile
import shutil
import subprocess
import asyncio
from urllib.parse import urlparse
import requests
from pathlib import Path
from datetime import datetime
import uuid

# Load environment variables first
import sys
import os
from pathlib import Path

# Add the project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from codegates.utils.env_loader import EnvironmentLoader
    # Force reload environment to ensure .env files are loaded
    EnvironmentLoader.load_environment(force_reload=True)
    print("✅ Environment loaded via EnvironmentLoader")
except ImportError:
    print("⚠️ EnvironmentLoader not available, using basic environment loading")
    # Fallback to basic dotenv loading
    try:
        from dotenv import load_dotenv
        load_dotenv()
        load_dotenv('.env')
        load_dotenv('config.env')
        print("✅ Environment loaded via dotenv")
    except ImportError:
        print("⚠️ python-dotenv not available, using system environment only")

# Try to import JIRA integration
try:
    from codegates.integrations.jira_integration import JiraIntegration
    JIRA_AVAILABLE = True
    print("✅ JIRA integration available")
except ImportError:
    JIRA_AVAILABLE = False
    print("⚠️ JIRA integration not available")

# Load configuration using ConfigLoader
try:
    from codegates.utils.config_loader import get_config
    config = get_config()
    
    # Get all configuration sections
    api_config = config.get_api_config()
    cors_config = config.get_cors_config()
    reports_config = config.get_reports_config()
    
    # Extract values
    API_HOST = api_config['host']
    API_PORT = api_config['port']
    API_BASE_URL = api_config['base_url'] or f"http://localhost:{API_PORT}"
    
    # DEBUG: Ensure API_BASE_URL has correct format
    if API_BASE_URL and not ':' in API_BASE_URL.replace('://', '').split('/')[0]:
        # If API_BASE_URL doesn't have a port, add the default port
        if API_BASE_URL.endswith('/'):
            API_BASE_URL = API_BASE_URL.rstrip('/')
        API_BASE_URL = f"{API_BASE_URL}:{API_PORT}"
        print(f"🔧 Fixed API_BASE_URL to include port: {API_BASE_URL}")
    
    API_VERSION_PREFIX = api_config['version_prefix']
    API_TITLE = api_config['title']
    API_DESCRIPTION = api_config['description']
    DOCS_ENABLED = api_config['docs_enabled']
    DOCS_URL = api_config['docs_url'] if DOCS_ENABLED else None
    REDOC_URL = api_config['redoc_url'] if DOCS_ENABLED else None
    
    # CORS settings
    CORS_ORIGINS = cors_config['origins']
    CORS_METHODS = cors_config['methods']
    CORS_HEADERS = cors_config['headers']
    CORS_EXPOSE_HEADERS = cors_config['expose_headers']
    
    print(f"✅ Configuration loaded successfully")
    print(f"   API: {API_BASE_URL}")
    print(f"   Host: {API_HOST}:{API_PORT}")
    
    # Validate configuration
    config_issues = config.validate_config()
    if config_issues:
        print("⚠️ Configuration issues found:")
        for issue in config_issues:
            print(f"   - {issue}")
    
except ImportError:
    print("⚠️ ConfigLoader not available, using fallback configuration")
    # Fallback to original hardcoded configuration
    API_HOST = os.getenv('CODEGATES_API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('CODEGATES_API_PORT', '8000'))
    API_BASE_URL = os.getenv('CODEGATES_API_BASE_URL', f'http://localhost:{API_PORT}')
    
    # DEBUG: Ensure API_BASE_URL has correct format (fallback section)
    if API_BASE_URL and not ':' in API_BASE_URL.replace('://', ''):
        # If API_BASE_URL doesn't have a port, add the default port
        if API_BASE_URL.endswith('/'):
            API_BASE_URL = API_BASE_URL.rstrip('/')
        API_BASE_URL = f"{API_BASE_URL}:{API_PORT}"
        print(f"🔧 Fixed fallback API_BASE_URL to include port: {API_BASE_URL}")
    
    API_VERSION_PREFIX = os.getenv('CODEGATES_API_VERSION_PREFIX', '/api/v1')
    API_TITLE = os.getenv('CODEGATES_API_TITLE', 'MyGates API')
    API_DESCRIPTION = os.getenv('CODEGATES_API_DESCRIPTION', 'API for validating code quality gates across different programming languages')
    DOCS_ENABLED = os.getenv('CODEGATES_API_DOCS_ENABLED', 'true').lower() == 'true'
    DOCS_URL = os.getenv('CODEGATES_API_DOCS_URL', '/docs') if DOCS_ENABLED else None
    REDOC_URL = os.getenv('CODEGATES_API_REDOC_URL', '/redoc') if DOCS_ENABLED else None
    
    # CORS Configuration from environment
    CORS_ORIGINS_STR = os.getenv('CODEGATES_CORS_ORIGINS', 'vscode-webview://*,http://localhost:*,http://127.0.0.1:*,https://localhost:*,https://127.0.0.1:*')
    CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(',')]
    CORS_METHODS_STR = os.getenv('CODEGATES_CORS_METHODS', 'GET,POST,PUT,DELETE,OPTIONS,PATCH')
    CORS_METHODS = [method.strip() for method in CORS_METHODS_STR.split(',')]
    CORS_HEADERS_STR = os.getenv('CODEGATES_CORS_HEADERS', 'Accept,Accept-Language,Content-Language,Content-Type,Authorization,X-Requested-With,User-Agent,Origin,Access-Control-Request-Method,Access-Control-Request-Headers')
    CORS_HEADERS = [header.strip() for header in CORS_HEADERS_STR.split(',')]
    CORS_EXPOSE_HEADERS_STR = os.getenv('CODEGATES_CORS_EXPOSE_HEADERS', 'Content-Type,Content-Length,Date,Server')
    CORS_EXPOSE_HEADERS = [header.strip() for header in CORS_EXPOSE_HEADERS_STR.split(',')]

# Create the main FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version="1.0.0"
)

# Configure CORS for the main app
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS
)

# Create a sub-application for /api/v1 routes
api_v1 = FastAPI(
    title="MyGates API v1",
    description="API v1 routes for MyGates",
)

# Configure CORS for the v1 sub-application
api_v1.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS
)

# In-memory storage for scan results (in production, use a database)
scan_results = {}

class ScanOptions(BaseModel):
    threshold: Optional[int] = Field(
        default=70,
        ge=0,
        le=100,
        description="Quality threshold percentage (0-100)"
    )

class JiraOptions(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable JIRA integration for this scan"
    )
    issue_key: Optional[str] = Field(
        None,
        description="JIRA issue key to post the report to (e.g., PROJECT-123)"
    )
    comment_format: Optional[str] = Field(
        default="markdown",
        description="Comment format: 'markdown' or 'text'"
    )
    include_details: Optional[bool] = Field(
        default=True,
        description="Include detailed gate results in the comment"
    )
    include_recommendations: Optional[bool] = Field(
        default=True,
        description="Include recommendations in the comment"
    )

class ScanRequest(BaseModel):
    repository_url: str = Field(
        ...,  # This makes it required
        description="Git repository URL (GitHub or GitHub Enterprise)"
    )
    branch: str = Field(
        default="main",
        description="Git branch to analyze"
    )
    github_token: Optional[str] = Field(
        None,
        description="GitHub token for private repositories (optional)"
    )
    scan_options: Optional[ScanOptions] = Field(
        default=None,
        description="Scan configuration options"
    )
    jira_options: Optional[JiraOptions] = Field(
        default=None,
        description="JIRA integration options (optional)"
    )

    @property
    def is_github_enterprise(self) -> bool:
        """Check if the repository URL is from GitHub Enterprise."""
        parsed_url = urlparse(self.repository_url)
        hostname = parsed_url.netloc.lower()
        # Check if it contains 'github' but is not github.com
        return 'github' in hostname and hostname != 'github.com'

    @property
    def is_github_com(self) -> bool:
        """Check if the repository URL is from github.com."""
        parsed_url = urlparse(self.repository_url)
        return parsed_url.netloc.lower() == 'github.com'

    def validate_github_url(self) -> bool:
        """Validate that this is a proper GitHub URL format."""
        try:
            parsed_url = urlparse(self.repository_url)
            
            # Check if it's a valid GitHub URL
            hostname = parsed_url.netloc.lower()
            if not ('github' in hostname):
                raise HTTPException(
                    status_code=400,
                    detail="Repository URL must be a GitHub.com or GitHub Enterprise URL (hostname must contain 'github')"
                )
            
            # Check path format (should be /owner/repo or /owner/repo.git)
            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid repository URL format. Expected: https://github.example.com/owner/repo"
                )
            
            # Clean up repo name if it ends with .git
            repo_name = path_parts[1]
            if repo_name.endswith('.git'):
                path_parts[1] = repo_name[:-4]
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid repository URL format: {str(e)}"
            )

    def check_repository_access(self):
        """Check if repository is accessible using git commands instead of GitHub API."""
        try:
            # First validate the URL format
            self.validate_github_url()
            
            # Parse repository URL
            parsed_url = urlparse(self.repository_url)
            path_parts = parsed_url.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid repository URL format"
                )
            
            owner = path_parts[0]
            repo = path_parts[1]
            
            # Clean up repo name if it ends with .git
            if repo.endswith('.git'):
                repo = repo[:-4]
            
            # Build the Git URL for testing
            if self.github_token:
                # Use token for authentication
                test_url = f"https://{self.github_token}@{parsed_url.netloc}{parsed_url.path}"
            else:
                # Try without token first
                test_url = f"https://{parsed_url.netloc}{parsed_url.path}"
            
            # Ensure URL ends with .git
            if not test_url.endswith('.git'):
                test_url += '.git'
            
            print(f"🔍 Testing repository access with git ls-remote: {parsed_url.netloc}{parsed_url.path}")
            
            # Use git ls-remote to test repository access
            # This works with both public/private repos and handles SSL certificates properly
            cmd = ["git", "ls-remote", "--heads", test_url]
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=30,
                    env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}  # Disable interactive prompts
                )
                
                if result.returncode == 0:
                    print(f"✅ Repository accessible")
                    return True
                else:
                    # Parse git error for better user messages
                    error_output = result.stderr.lower()
                    
                    if 'authentication failed' in error_output or 'could not read username' in error_output:
                        if self.github_token:
                            raise HTTPException(
                                status_code=401,
                                detail="Invalid GitHub token or insufficient permissions. Please check if the token has 'repo' scope access."
                            )
                        else:
                            raise HTTPException(
                                status_code=401,
                                detail="Repository is private or authentication required. Please provide a GitHub token with 'repo' scope."
                            )
                    elif 'repository not found' in error_output or 'not found' in error_output:
                        raise HTTPException(
                            status_code=404,
                            detail="Repository not found. Please check the repository URL."
                        )
                    elif 'permission denied' in error_output:
                        raise HTTPException(
                            status_code=403,
                            detail="Permission denied. Please check if the token has access to this repository."
                        )
                    elif 'ssl certificate' in error_output or 'certificate verify failed' in error_output:
                        # For SSL certificate issues, suggest using token or configuring git
                        raise HTTPException(
                            status_code=400,
                            detail="SSL certificate verification failed. This is common with GitHub Enterprise. Please provide a GitHub token for authentication."
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cannot access repository: {result.stderr.strip()}"
                        )
                        
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=408,
                    detail="Repository access test timed out. Please check the repository URL and network connectivity."
                )
                
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to validate repository access: {str(e)}"
            )

class GateResult(BaseModel):
    name: str = Field(..., description="Name of the quality gate")
    status: str = Field(..., description="Gate status: 'PASS' | 'FAIL' | 'WARNING' | 'NOT_APPLICABLE'")
    score: float = Field(..., ge=0, le=100, description="Gate score (0-100)")
    details: List[str] = Field(default_factory=list, description="Detailed findings")
    expected: Optional[int] = Field(None, description="Expected number of implementations")
    found: Optional[int] = Field(None, description="Actual number found")
    coverage: Optional[float] = Field(None, ge=0, le=100, description="Coverage percentage")
    quality_score: Optional[float] = Field(None, ge=0, le=100, description="Quality score")

class ScanResult(BaseModel):
    scan_id: str = Field(..., description="Unique scan identifier")
    status: str = Field(..., description="Scan status: 'completed' | 'failed' | 'running'")
    score: float = Field(..., ge=0, le=100, description="Overall quality score (0-100)")
    gates: List[GateResult] = Field(default_factory=list, description="Individual gate results")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    report_url: Optional[str] = Field(None, description="URL to detailed report")
    jira_result: Optional[Dict[str, Any]] = Field(None, description="JIRA integration result")

def ensure_writable_directory(path: str, description: str = "directory") -> str:
    """Ensure directory exists and is writable, with container-friendly fallbacks"""
    
    # List of fallback options
    fallback_options = [
        path,
        f"./app/{Path(path).name}",  # App-relative path
        f"./{Path(path).name}",      # Current dir relative
        f"./temp/{Path(path).name}"  # Temp subdirectory
    ]
    
    for option in fallback_options:
        if not option:
            continue
            
        try:
            # Create directory if it doesn't exist
            os.makedirs(option, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(option, f'.write_test_{os.getpid()}')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            print(f"✅ Using {description}: {option}")
            return option
            
        except (OSError, PermissionError) as e:
            print(f"⚠️ Cannot use {option} for {description}: {e}")
            continue
    
    # If all options failed, raise an error
    raise Exception(f"No writable {description} found. Please set appropriate environment variables or ensure container has write permissions.")

def clone_repository(repo_url: str, branch: str, token: Optional[str] = None) -> str:
    """Clone repository to temporary directory with OCP container support"""
    
    # Try multiple temporary directory options for container compatibility
    temp_base_options = [
        os.environ.get('TEMP_REPO_DIR'),  # User-configured
        os.environ.get('TMPDIR'),         # System temp (containers)
        '/tmp',                           # Standard temp
        './temp',                         # Local temp (fallback)
        '.'                               # Current directory (last resort)
    ]
    
    temp_dir = None
    for temp_base in temp_base_options:
        if not temp_base:
            continue
            
        try:
            # Ensure base directory exists and is writable
            os.makedirs(temp_base, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(temp_base, f'.write_test_{os.getpid()}')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            # Create unique temporary directory
            temp_dir = tempfile.mkdtemp(prefix="mygates_", dir=temp_base)
            print(f"📁 Using temporary directory: {temp_dir}")
            break
            
        except (OSError, PermissionError) as e:
            print(f"⚠️ Cannot use {temp_base}: {e}")
            continue
    
    if not temp_dir:
        raise Exception("No writable temporary directory found. Set TEMP_REPO_DIR environment variable to a writable path.")
    
    try:
        # Build clone URL
        parsed_url = urlparse(repo_url)
        if token:
            clone_url = f"https://{token}@{parsed_url.netloc}{parsed_url.path}.git"
        else:
            clone_url = f"https://{parsed_url.netloc}{parsed_url.path}.git"
        
        # Clone repository with enhanced error handling
        cmd = ["git", "clone", "-b", branch, "--depth", "1", clone_url, temp_dir]
        print(f"🔄 Running: git clone -b {branch} --depth 1 [URL] {temp_dir}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            print(f"❌ Git clone failed: {error_msg}")
            
            # Enhanced error messages for containers
            if 'permission denied' in error_msg.lower():
                raise Exception(f"Permission denied during git clone. This might be due to container security constraints. Error: {error_msg}")
            else:
                raise Exception(f"Git clone failed: {error_msg}")
        
        print(f"✅ Repository cloned successfully to {temp_dir}")
        return temp_dir
        
    except Exception as e:
        # Cleanup on failure
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                print(f"⚠️ Failed to cleanup {temp_dir}: {cleanup_error}")
        raise e

def analyze_repository(repo_path: str, threshold: int, repository_url: Optional[str] = None) -> Dict:
    """Analyze repository using CodeGates"""
    try:
        # Try to import and use the actual CodeGates analysis
        try:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from codegates.core.gate_validator import GateValidator
            from codegates.core.language_detector import LanguageDetector
            from codegates.models import ScanConfig, Language
            
            # Try to import LLM components
            llm_manager = None
            try:
                from codegates.core.llm_analyzer import LLMIntegrationManager, LLMConfig, LLMProvider
                from codegates.utils.env_loader import EnvironmentLoader
                
                # Get LLM configuration from EnvironmentLoader
                env_loader = EnvironmentLoader()
                preferred_provider = env_loader.get_preferred_llm_provider()
                
                if preferred_provider:
                    provider_config = env_loader.get_llm_config(preferred_provider)
                    print(f"🔧 Using {preferred_provider} LLM provider")
                    print(f"   Configuration: {provider_config}")
                    
                    if preferred_provider == 'openai':
                        llm_config = LLMConfig(
                            provider=LLMProvider.OPENAI,
                            model=provider_config['model'],
                            api_key=provider_config['api_key'],
                            base_url=provider_config.get('base_url'),
                            temperature=provider_config['temperature'],
                            max_tokens=provider_config['max_tokens']
                        )
                    elif preferred_provider == 'anthropic':
                        llm_config = LLMConfig(
                            provider=LLMProvider.ANTHROPIC,
                            model=provider_config['model'],
                            api_key=provider_config['api_key'],
                            base_url=provider_config.get('base_url'),
                            temperature=provider_config['temperature'],
                            max_tokens=provider_config['max_tokens']
                        )
                    elif preferred_provider == 'local':
                        llm_config = LLMConfig(
                            provider=LLMProvider.LOCAL,
                            model=provider_config['model'],
                            api_key=provider_config['api_key'],
                            base_url=provider_config['base_url'],
                            temperature=provider_config['temperature'],
                            max_tokens=provider_config['max_tokens']
                        )
                    else:
                        print(f"⚠️ Unsupported provider: {preferred_provider}")
                        llm_config = None
                    
                    if llm_config:
                        llm_manager = LLMIntegrationManager(llm_config)
                        
                        # Test if LLM is available
                        if llm_manager.is_enabled():
                            print(f"✅ LLM integration enabled with {preferred_provider}")
                        else:
                            print(f"⚠️ LLM integration failed for {preferred_provider}, continuing with pattern-based analysis")
                            llm_manager = None
                else:
                    print("⚠️ No LLM provider configured")
                    print("📝 To enable LLM analysis:")
                    print("   Option 1: Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
                    print("   Option 2: Configure local LLM service in .env file")
                    print("   Continuing with pattern-based analysis only...")
                    llm_manager = None
                        
            except ImportError:
                print("⚠️ LLM components not available, continuing with pattern-based analysis only")
                llm_manager = None
            
            # Detect languages
            detector = LanguageDetector()
            languages = detector.detect_languages(Path(repo_path))
            
            if not languages:
                languages = [Language.PYTHON]  # Default fallback
            
            print(f"🔍 Detected languages: {[lang.value for lang in languages]}")
            
            # Create scan configuration
            config = ScanConfig(
                target_path=repo_path,
                languages=languages,
                min_coverage_threshold=threshold,
                exclude_patterns=[
                    "node_modules/**", ".git/**", "**/__pycache__/**",
                    "**/target/**", "**/bin/**", "**/obj/**", "**/.vscode/**"
                ],
                max_file_size=1024*1024  # 1MB max file size
            )
            
            # Run validation
            validator = GateValidator(config)
            result = validator.validate(Path(repo_path), llm_manager, repository_url)
            
            print(f"📊 Analysis completed. Overall score: {result.overall_score:.1f}%")
            print(f"📈 Gates analyzed: {len(result.gate_scores)}")
            
            # Convert to API format
            gates = []
            for gate_score in result.gate_scores:
                # Handle different status types including NOT_APPLICABLE
                if gate_score.status == "NOT_APPLICABLE":
                    status = "NOT_APPLICABLE"
                elif gate_score.final_score >= 80:
                    status = "PASS"
                elif gate_score.final_score >= 60:
                    status = "WARNING"
                else:
                    status = "FAIL"
                
                # Limit details to avoid overwhelming the response
                details = gate_score.details[:5] if gate_score.details else [
                    f"Expected: {gate_score.expected}, Found: {gate_score.found}",
                    f"Coverage: {gate_score.coverage:.1f}%"
                ]
                
                gates.append({
                    "name": gate_score.gate.value,
                    "status": status,
                    "score": gate_score.final_score,
                    "details": details,
                    "expected": gate_score.expected,
                    "found": gate_score.found,
                    "coverage": gate_score.coverage,
                    "quality_score": gate_score.quality_score
                })
            
            return {
                "score": result.overall_score,
                "gates": gates,
                "recommendations": result.recommendations[:5] if result.recommendations else [
                    "Implement structured logging across your codebase",
                    "Add comprehensive error handling",
                    "Include automated tests for critical functionality"
                ],
                "llm_enhanced": llm_manager is not None,
                "languages_detected": [lang.value for lang in languages],
                "total_files": result.total_files,
                "total_lines": result.total_lines,
                "result_object": result  # Include full result for HTML generation
            }
            
        except ImportError as e:
            print(f"CodeGates import failed: {e}")
            # Fallback analysis
            return perform_basic_analysis(repo_path, threshold)
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        # Return basic analysis as fallback
        return perform_basic_analysis(repo_path, threshold)

def perform_basic_analysis(repo_path: str, threshold: int) -> Dict:
    """Perform basic analysis when CodeGates is not available"""
    
    # Count files by type
    file_counts = {}
    total_files = 0
    
    for root, dirs, files in os.walk(repo_path):
        # Skip common directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', 'target', 'bin', 'obj']]
        
        for file in files:
            total_files += 1
            ext = os.path.splitext(file)[1].lower()
            file_counts[ext] = file_counts.get(ext, 0) + 1
    
    # Basic scoring based on file types and structure
    score = 50  # Base score
    
    # Language detection and scoring
    gates = []
    
    # Check for common quality indicators
    has_tests = any(ext in ['.test.js', '.spec.js', '.test.py', '.spec.py'] or 'test' in ext for ext in file_counts.keys())
    has_config = any(file in ['package.json', 'requirements.txt', 'pom.xml', 'build.gradle'] for file in os.listdir(repo_path) if os.path.isfile(os.path.join(repo_path, file)))
    has_readme = any(file.lower().startswith('readme') for file in os.listdir(repo_path) if os.path.isfile(os.path.join(repo_path, file)))
    
    # Test coverage gate
    test_score = 80 if has_tests else 30
    gates.append({
        "name": "automated_tests",
        "status": "PASS" if test_score >= 70 else "FAIL",
        "score": test_score,
        "details": ["Test files found" if has_tests else "No test files detected"]
    })
    
    # Configuration gate
    config_score = 90 if has_config else 40
    gates.append({
        "name": "project_structure",
        "status": "PASS" if config_score >= 70 else "FAIL", 
        "score": config_score,
        "details": ["Configuration files found" if has_config else "No configuration files detected"]
    })
    
    # Documentation gate
    doc_score = 85 if has_readme else 35
    gates.append({
        "name": "documentation",
        "status": "PASS" if doc_score >= 70 else "FAIL",
        "score": doc_score,
        "details": ["README file found" if has_readme else "No README file detected"]
    })
    
    # Calculate overall score
    overall_score = sum(gate["score"] for gate in gates) / len(gates) if gates else 50
    
    recommendations = []
    if not has_tests:
        recommendations.append("Add automated tests to improve code quality")
    if not has_config:
        recommendations.append("Add configuration files (package.json, requirements.txt, etc.)")
    if not has_readme:
        recommendations.append("Add README documentation")
    
    return {
        "score": overall_score,
        "gates": gates,
        "recommendations": recommendations,
        "llm_enhanced": False
    }

async def perform_scan(scan_id: str, request: ScanRequest):
    """Perform the actual repository scan with timeout handling"""
    try:
        # Update status to running
        scan_results[scan_id]["status"] = "running"
        scan_results[scan_id]["message"] = "Cloning repository..."
        
        # Clone repository
        repo_path = clone_repository(
            request.repository_url, 
            request.branch, 
            request.github_token
        )
        
        try:
            scan_results[scan_id]["message"] = "Analyzing repository with optimized LLM processing..."
            
            # Analyze repository with timeout
            threshold = request.scan_options.threshold if request.scan_options else 70
            
            # Use asyncio timeout for better control
            try:
                analysis_result = await asyncio.wait_for(
                    asyncio.to_thread(analyze_repository, repo_path, threshold, request.repository_url),
                    timeout=180.0  # 3 minutes timeout
                )
                
                # Update scan results
                scan_results[scan_id].update({
                    "status": "completed",
                    "score": analysis_result["score"],
                    "gates": analysis_result["gates"],
                    "recommendations": analysis_result["recommendations"],
                    "report_url": f"{API_BASE_URL}{API_VERSION_PREFIX}/reports/{scan_id}",
                    "message": f"Scan completed {'with LLM enhancement' if analysis_result.get('llm_enhanced') else 'with pattern-based analysis'}",
                    "completed_at": datetime.now().isoformat(),
                    "llm_enhanced": analysis_result.get('llm_enhanced', False),
                    "total_files": analysis_result.get('total_files', 0),
                    "total_lines": analysis_result.get('total_lines', 0),
                    "result_object": analysis_result.get('result_object'),  # Store full result for HTML generation
                    "repository_url": request.repository_url,  # Store repository URL
                    "branch": request.branch  # Store branch
                })
                
                # Generate and save HTML report immediately
                try:
                    validation_result = analysis_result.get('result_object')
                    if validation_result:
                        from codegates.reports import ReportGenerator
                        from codegates.models import ReportConfig
                        
                        # Create reports directory with container-friendly fallbacks
                        reports_dir_path = ensure_writable_directory("reports", "reports directory")
                        reports_dir = Path(reports_dir_path)
                        
                        # Generate and save report to file
                        report_filename = f"hard_gate_report_{scan_id}.html"
                        report_path = reports_dir / report_filename
                        
                        # Create report config for HTML generation
                        report_config = ReportConfig(
                            format='html',
                            output_path=str(reports_dir),
                            include_details=True,
                            include_recommendations=True
                        )
                        
                        # Generate HTML report
                        generator = ReportGenerator(report_config)
                        html_content = generator._generate_html_content(validation_result)
                        
                        # Save the HTML file
                        with open(report_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        print(f"📄 HTML report saved to: {report_path}")
                        scan_results[scan_id]["report_file"] = str(report_path)
                        
                except Exception as report_error:
                    print(f"⚠️ Failed to generate HTML report: {report_error}")
                    # Continue without failing the scan
                
                # Log API_BASE_URL for debugging
                print(f"🔍 DEBUG: API_BASE_URL = '{API_BASE_URL}'")
                print(f"🔍 DEBUG: API_VERSION_PREFIX = '{API_VERSION_PREFIX}'")
                print(f"🔍 DEBUG: Full report URL = '{API_BASE_URL}{API_VERSION_PREFIX}/reports/{scan_id}'")
                
                # JIRA Integration (if enabled and available)
                jira_result = None
                if (JIRA_AVAILABLE and 
                    request.jira_options and 
                    request.jira_options.enabled and 
                    analysis_result.get('result_object')):
                    
                    try:
                        scan_results[scan_id]["message"] = "Posting report to JIRA..."
                        
                        # Create JIRA integration instance
                        jira_config = {}
                        if request.jira_options.comment_format:
                            jira_config['comment_format'] = request.jira_options.comment_format
                        if request.jira_options.include_details is not None:
                            jira_config['include_details'] = request.jira_options.include_details
                        if request.jira_options.include_recommendations is not None:
                            jira_config['include_recommendations'] = request.jira_options.include_recommendations
                        
                        jira_integration = JiraIntegration(jira_config if jira_config else None)
                        
                        if jira_integration.is_available():
                            # Prepare additional context
                            additional_context = {
                                'repository_url': request.repository_url,
                                'branch': request.branch,
                                'scan_id': scan_id,
                                'report_url': f"{API_BASE_URL}{API_VERSION_PREFIX}/reports/{scan_id}"
                            }
                            
                            # Post to JIRA
                            jira_result = jira_integration.post_report_comment(
                                analysis_result['result_object'],
                                request.jira_options.issue_key,
                                additional_context
                            )
                            
                            if jira_result.get('success'):
                                print(f"✅ Report posted to JIRA issue {jira_result.get('jira_issue')}")
                                scan_results[scan_id]["message"] += f" | Posted to JIRA: {jira_result.get('jira_issue')}"
                            else:
                                print(f"⚠️ JIRA posting failed: {jira_result.get('message')}")
                        else:
                            jira_result = {
                                'success': False,
                                'message': 'JIRA integration not properly configured',
                                'posted': False
                            }
                            
                    except Exception as jira_error:
                        print(f"⚠️ JIRA integration error: {str(jira_error)}")
                        jira_result = {
                            'success': False,
                            'message': f'JIRA integration failed: {str(jira_error)}',
                            'posted': False,
                            'error': str(jira_error)
                        }
                
                # Store JIRA result
                if jira_result:
                    scan_results[scan_id]["jira_result"] = jira_result
                
            except asyncio.TimeoutError:
                print("⏰ Repository scan timed out after 3 minutes")
                scan_results[scan_id].update({
                    "status": "completed",
                    "score": 0.0,
                    "gates": [],
                    "recommendations": [
                        "Scan timed out after 3 minutes",
                        "Try scanning a smaller repository or specific directory",
                        "Consider disabling LLM analysis for faster results"
                    ],
                    "report_url": f"{API_BASE_URL}{API_VERSION_PREFIX}/reports/{scan_id}",
                    "message": "Scan timed out - completed with basic analysis only",
                    "error": "timeout",
                    "completed_at": datetime.now().isoformat()
                })
                
        finally:
            # Cleanup cloned repository
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
                
    except Exception as e:
        print(f"❌ Scan failed for {scan_id}: {str(e)}")
        scan_results[scan_id].update({
            "status": "failed",
            "message": f"Scan failed: {str(e)}",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })

@api_v1.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight requests for all routes"""
    return {"message": "OK"}

@api_v1.get("/health")
async def health_check():
    """Check API health status."""
    return {"status": "healthy", "cors_enabled": True}

@api_v1.post("/scan", response_model=ScanResult)
async def scan_repository(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Scan a Git repository for code quality.
    
    - Supports both GitHub.com and GitHub Enterprise repositories
    - GitHub token is optional for public repositories
    - GitHub token is required for private repositories
    - Validates repository URL and branch
    - Returns detailed quality analysis results
    """
    try:
        # Check repository access (handles public/private repos)
        request.check_repository_access()

        # Generate scan ID
        scan_id = str(uuid.uuid4())
        
        # Initialize scan result
        scan_results[scan_id] = {
            "scan_id": scan_id,
            "status": "running",
            "score": 0.0,
            "gates": [],
            "recommendations": [],
            "report_url": None,
            "message": "Scan initiated",
            "created_at": datetime.now().isoformat()
        }
        
        # Start background scan
        background_tasks.add_task(perform_scan, scan_id, request)
        
        return ScanResult(
            scan_id=scan_id,
            status="running",
            score=0.0,
            gates=[],
            recommendations=[],
            report_url=None
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_v1.get("/scan/{scan_id}/status", response_model=ScanResult)
async def get_scan_status(scan_id: str):
    """Get the status and results of a specific scan."""
    try:
        if scan_id not in scan_results:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        result = scan_results[scan_id]
        
        return ScanResult(
            scan_id=result["scan_id"],
            status=result["status"],
            score=result["score"],
            gates=[GateResult(**gate) for gate in result["gates"]],
            recommendations=result["recommendations"],
            report_url=result.get("report_url"),
            jira_result=result.get("jira_result")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_v1.get("/reports/{scan_id}")
async def get_html_report(scan_id: str):
    """Generate and return HTML report for a scan."""
    try:
        if scan_id not in scan_results:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        result = scan_results[scan_id]
        
        if result["status"] != "completed":
            raise HTTPException(status_code=400, detail="Scan not completed yet")
        
        # First, try to serve from saved file
        if "report_file" in result:
            report_path = Path(result["report_file"])
            if report_path.exists():
                try:
                    with open(report_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    return HTMLResponse(content=html_content, status_code=200)
                except Exception as file_error:
                    print(f"⚠️ Failed to read saved report file: {file_error}")
                    # Fall through to regeneration
        
        # Try to find report file by scan_id if not stored in result
        reports_dir = Path("reports")
        report_filename = f"hard_gate_report_{scan_id}.html"
        report_path = reports_dir / report_filename
        
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                return HTMLResponse(content=html_content, status_code=200)
            except Exception as file_error:
                print(f"⚠️ Failed to read report file: {file_error}")
                # Fall through to regeneration
        
        # If no saved file exists, generate on-demand
        print(f"📄 No saved report found for {scan_id}, generating on-demand...")
        
        # Get the full validation result object
        validation_result = result.get("result_object")
        
        if not validation_result:
            raise HTTPException(status_code=500, detail="Report data not available")
        
        # Generate HTML report
        try:
            from codegates.reports import ReportGenerator
            from codegates.models import ReportConfig
            
            # Create reports directory with container-friendly fallbacks
            reports_dir_path = ensure_writable_directory("reports", "reports directory")
            reports_dir = Path(reports_dir_path)
            
            # Generate and save report to file
            report_filename = f"hard_gate_report_{scan_id}.html"
            report_path = reports_dir / report_filename
            
            # Create report config for HTML generation
            report_config = ReportConfig(
                format='html',
                output_path=str(reports_dir),
                include_details=True,
                include_recommendations=True
            )
            
            # Generate HTML report
            generator = ReportGenerator(report_config)
            html_content = generator._generate_html_content(validation_result)
            
            # Save the HTML file
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"📄 HTML report saved to: {report_path}")
            scan_results[scan_id]["report_file"] = str(report_path)
            
            return HTMLResponse(content=html_content, status_code=200)
            
        except ImportError:
            # Fallback to basic HTML if report generator not available
            
            # Extract project name from repository URL 
            project_name = "Unknown Project"
            repository_url = result.get("repository_url")
            if repository_url:
                try:
                    url_parts = repository_url.rstrip('/').split('/')
                    if len(url_parts) >= 2:
                        project_name = url_parts[-1]
                        if project_name.endswith('.git'):
                            project_name = project_name[:-4]
                except Exception:
                    project_name = "Unknown Project"
            
            basic_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Hard Gate Assessment - {project_name}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .score {{ font-size: 24px; color: #2563eb; font-weight: bold; }}
                    .gate {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; }}
                    .pass {{ background-color: #ecfdf5; }}
                    .fail {{ background-color: #fef2f2; }}
                    .warning {{ background-color: #fffbeb; }}
                </style>
            </head>
            <body>
                <h1>{project_name}</h1>
                <p style="color: #2563eb; margin-bottom: 30px; font-weight: 500;">Hard Gate Assessment Report</p>
                <div class="score">Overall Score: {result['score']:.1f}%</div>
                <h2>Gate Results</h2>
                {''.join([f'<div class="gate {gate["status"].lower()}"><strong>{gate["name"]}</strong>: {gate["status"]} ({gate["score"]:.1f}%)</div>' for gate in result["gates"]])}
                <h2>Recommendations</h2>
                <ul>
                    {''.join([f'<li>{rec}</li>' for rec in result["recommendations"]])}
                </ul>
            </body>
            </html>
            """
            
            # Save basic report to file as well
            reports_dir_path = ensure_writable_directory("reports", "reports directory")
            reports_dir = Path(reports_dir_path)
            report_filename = f"hard_gate_report_{scan_id}.html"
            report_path = reports_dir / report_filename
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(basic_html)
            
            # Update scan result with report file path
            scan_results[scan_id]["report_file"] = str(report_path)
            
            return HTMLResponse(content=basic_html, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_v1.get("/reports")
async def list_reports():
    """List all available saved reports."""
    try:
        reports_dir = Path("reports")
        
        if not reports_dir.exists():
            return {"reports": []}
        
        reports = []
        for report_file in reports_dir.glob("hard_gate_report_*.html"):
            try:
                # Extract scan_id from filename
                scan_id = report_file.stem.replace("hard_gate_report_", "")
                
                # Get file stats
                stat = report_file.stat()
                
                # Check if we have scan result data
                scan_data = scan_results.get(scan_id, {})
                
                reports.append({
                    "scan_id": scan_id,
                    "filename": report_file.name,
                    "file_size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "score": scan_data.get("score"),
                    "status": scan_data.get("status", "unknown"),
                    "report_url": f"{API_BASE_URL}{API_VERSION_PREFIX}/reports/{scan_id}"
                })
                
            except Exception as e:
                print(f"⚠️ Error processing report file {report_file}: {e}")
                continue
        
        # Sort by creation time (newest first)
        reports.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "reports": reports,
            "total_count": len(reports)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_v1.get("/jira/status")
async def get_jira_status():
    """Get JIRA integration status and configuration."""
    try:
        if not JIRA_AVAILABLE:
            return {
                "available": False,
                "message": "JIRA integration module not available"
            }
        
        jira_integration = JiraIntegration()
        connection_test = jira_integration.test_connection()
        
        return {
            "available": JIRA_AVAILABLE,
            "enabled": jira_integration.is_available(),
            "configuration": {
                "jira_url": jira_integration.jira_url if jira_integration.enabled else None,
                "username": jira_integration.username if jira_integration.enabled else None,
                "comment_format": jira_integration.comment_format if jira_integration.enabled else None,
            },
            "connection_test": connection_test
        }
        
    except Exception as e:
        return {
            "available": JIRA_AVAILABLE,
            "enabled": False,
            "error": str(e)
        }

class JiraPostRequest(BaseModel):
    scan_id: str = Field(..., description="Scan ID to post to JIRA")
    issue_key: str = Field(..., description="JIRA issue key (e.g., PROJECT-123)")
    comment_format: Optional[str] = Field(default="markdown", description="Comment format: 'markdown' or 'text'")
    include_details: Optional[bool] = Field(default=True, description="Include detailed gate results")
    include_recommendations: Optional[bool] = Field(default=True, description="Include recommendations")

@api_v1.post("/jira/post")
async def post_to_jira(request: JiraPostRequest):
    """Manually post a scan report to JIRA."""
    try:
        if not JIRA_AVAILABLE:
            raise HTTPException(status_code=500, detail="JIRA integration not available")
        
        # Check if scan exists
        if request.scan_id not in scan_results:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        result = scan_results[request.scan_id]
        
        if result["status"] != "completed":
            raise HTTPException(status_code=400, detail="Scan not completed yet")
        
        validation_result = result.get("result_object")
        if not validation_result:
            raise HTTPException(status_code=500, detail="Scan result data not available")
        
        # Create JIRA integration with custom config
        jira_config = {
            'comment_format': request.comment_format,
            'include_details': request.include_details,
            'include_recommendations': request.include_recommendations
        }
        
        jira_integration = JiraIntegration(jira_config)
        
        if not jira_integration.is_available():
            raise HTTPException(status_code=500, detail="JIRA integration not properly configured")
        
        # Prepare additional context
        additional_context = {
            'scan_id': request.scan_id,
            'report_url': f"{API_BASE_URL}{API_VERSION_PREFIX}/reports/{request.scan_id}"
        }
        
        # Post to JIRA
        jira_result = jira_integration.post_report_comment(
            validation_result,
            request.issue_key,
            additional_context
        )
        
        return jira_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount the v1 API router
app.mount("/api/v1", api_v1)

def start_server():
    uvicorn.run(app, host=API_HOST, port=API_PORT)

if __name__ == "__main__":
    start_server() 