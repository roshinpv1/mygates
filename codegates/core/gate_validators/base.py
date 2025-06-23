"""
Base Gate Validator - Abstract base class for all gate validators
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor
import json

from ...models import Language, FileAnalysis
from pydantic import BaseModel


class GateValidationResult(BaseModel):
    """Result of gate validation"""
    expected: int
    found: int
    quality_score: float
    details: List[str] = []
    recommendations: List[str] = []
    technologies: Dict[str, List[str]] = {}  # New field for detected technologies
    matches: List[Dict[str, Any]] = []  # Code matches found during validation


class BaseGateValidator(ABC):
    """Abstract base class for gate validators"""
    
    def __init__(self, language: Language):
        self.language = language
        self.patterns = self._get_language_patterns()
        self.config_patterns = self._get_config_patterns()
        self.technology_patterns = self._get_technology_patterns()
    
    @abstractmethod
    def validate(self, target_path: Path, 
                file_analyses: List[FileAnalysis]) -> GateValidationResult:
        """Validate gate implementation"""
        pass
    
    @abstractmethod
    def _get_language_patterns(self) -> Dict[str, List[str]]:
        """Get language-specific patterns for validation"""
        pass
    
    @abstractmethod
    def _get_config_patterns(self) -> Dict[str, List[str]]:
        """Get configuration file patterns"""
        pass
    
    def _get_technology_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Get technology detection patterns by category"""
        
        if self.language == Language.PYTHON:
            return {
                'logging': {
                    'loguru': [r'from loguru import', r'import loguru', r'loguru\.'],
                    'structlog': [r'import structlog', r'structlog\.'],
                    'python-json-logger': [r'pythonjsonlogger', r'JsonFormatter'],
                    'logging': [r'import logging', r'logging\.'],
                },
                'web_frameworks': {
                    'fastapi': [r'from fastapi import', r'FastAPI\(', r'@app\.'],
                    'flask': [r'from flask import', r'Flask\(', r'@app\.route'],
                    'django': [r'from django', r'django\.', r'urls\.py'],
                    'starlette': [r'from starlette', r'Starlette\('],
                },
                'async': {
                    'asyncio': [r'import asyncio', r'async def', r'await '],
                    'aiohttp': [r'import aiohttp', r'aiohttp\.'],
                    'aiofiles': [r'import aiofiles', r'aiofiles\.'],
                },
                'testing': {
                    'pytest': [r'import pytest', r'@pytest\.', r'def test_'],
                    'unittest': [r'import unittest', r'unittest\.TestCase'],
                    'mock': [r'from unittest.mock', r'@mock\.'],
                },
                'database': {
                    'sqlalchemy': [r'from sqlalchemy', r'sqlalchemy\.'],
                    'django-orm': [r'from django.db', r'models\.Model'],
                    'pymongo': [r'import pymongo', r'pymongo\.'],
                    'redis': [r'import redis', r'redis\.'],
                },
                'monitoring': {
                    'sentry': [r'import sentry_sdk', r'sentry_sdk\.'],
                    'prometheus': [r'prometheus_client', r'prometheus\.'],
                    'datadog': [r'datadog', r'ddtrace'],
                },
            }
        elif self.language == Language.JAVA:
            return {
                'logging': {
                    'logback': [r'logback\.xml', r'ch\.qos\.logback'],
                    'log4j': [r'log4j', r'org\.apache\.log4j'],
                    'slf4j': [r'org\.slf4j', r'import.*slf4j'],
                },
                'web_frameworks': {
                    'spring-boot': [r'@SpringBootApplication', r'@RestController', r'@RequestMapping'],
                    'spring-mvc': [r'@Controller', r'@RequestMapping'],
                    'jersey': [r'@Path', r'@GET', r'@POST'],
                    'servlet': [r'HttpServlet', r'@WebServlet'],
                },
                'testing': {
                    'junit': [r'@Test', r'import.*junit', r'org\.junit'],
                    'mockito': [r'import.*mockito', r'@Mock'],
                    'testng': [r'import.*testng', r'@Test'],
                },
                'database': {
                    'hibernate': [r'@Entity', r'@Table', r'hibernate'],
                    'jpa': [r'@Entity', r'javax\.persistence'],
                    'jdbc': [r'java\.sql', r'DriverManager'],
                },
                'monitoring': {
                    'micrometer': [r'micrometer', r'@Timed'],
                    'actuator': [r'spring-boot-actuator', r'@Endpoint'],
                },
            }
        elif self.language in [Language.JAVASCRIPT, Language.TYPESCRIPT]:
            return {
                'logging': {
                    'winston': [r'require\(["\']winston', r'import.*winston', r'winston\.'],
                    'bunyan': [r'require\(["\']bunyan', r'bunyan\.'],
                    'pino': [r'require\(["\']pino', r'pino\('],
                    'console': [r'console\.log', r'console\.error'],
                },
                'web_frameworks': {
                    'express': [r'require\(["\']express', r'express\(', r'app\.get'],
                    'koa': [r'require\(["\']koa', r'new Koa'],
                    'fastify': [r'require\(["\']fastify', r'fastify\('],
                    'nestjs': [r'@nestjs', r'@Controller', r'@Injectable'],
                },
                'frontend': {
                    'react': [r'import.*react', r'from ["\']react', r'React\.'],
                    'vue': [r'import.*vue', r'Vue\.', r'@Component'],
                    'angular': [r'@angular', r'@Component', r'@Injectable'],
                },
                'testing': {
                    'jest': [r'describe\(', r'it\(', r'test\(', r'expect\('],
                    'mocha': [r'require\(["\']mocha', r'describe\(', r'it\('],
                    'cypress': [r'cy\.', r'cypress'],
                },
                'monitoring': {
                    'sentry': [r'@sentry', r'Sentry\.'],
                    'datadog': [r'dd-trace', r'datadog'],
                },
            }
        elif self.language == Language.CSHARP:
            return {
                'logging': {
                    'serilog': [r'using Serilog', r'Log\.', r'Serilog\.'],
                    'nlog': [r'using NLog', r'NLog\.'],
                    'ilogger': [r'ILogger<', r'_logger\.Log'],
                },
                'web_frameworks': {
                    'asp.net-core': [r'Microsoft\.AspNetCore', r'\[ApiController\]', r'\[Route'],
                    'mvc': [r'Controller', r'ActionResult'],
                    'web-api': [r'\[ApiController\]', r'\[HttpGet\]'],
                },
                'testing': {
                    'xunit': [r'using Xunit', r'\[Fact\]', r'\[Theory\]'],
                    'nunit': [r'using NUnit', r'\[Test\]'],
                    'mstest': [r'Microsoft\.VisualStudio\.TestTools', r'\[TestMethod\]'],
                },
                'database': {
                    'entity-framework': [r'using.*EntityFramework', r'DbContext'],
                    'dapper': [r'using Dapper', r'Dapper\.'],
                },
                'monitoring': {
                    'application-insights': [r'Microsoft\.ApplicationInsights', r'TelemetryClient'],
                },
            }
        else:
            return {}
    
    def _detect_technologies(self, target_path: Path, file_analyses: List[FileAnalysis]) -> Dict[str, List[str]]:
        """Detect technologies used in the codebase"""
        
        detected_technologies = {}
        
        # Get relevant files for this language
        relevant_files = [f for f in file_analyses if f.language == self.language]
        
        for category, tech_patterns in self.technology_patterns.items():
            detected_technologies[category] = []
            
            for tech_name, patterns in tech_patterns.items():
                found = False
                
                # Check in code files
                for file_analysis in relevant_files:
                    try:
                        file_path = target_path / file_analysis.file_path
                        if file_path.exists() and file_path.is_file():
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            
                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                                    found = True
                                    break
                            
                            if found:
                                break
                    except Exception:
                        continue
                
                # Check in config files
                if not found:
                    config_files = [
                        'package.json', 'requirements.txt', 'pom.xml', 'build.gradle',
                        'Gemfile', 'composer.json', 'project.json', '*.csproj'
                    ]
                    
                    for config_file in config_files:
                        try:
                            config_path = target_path / config_file
                            if config_path.exists():
                                content = config_path.read_text(encoding='utf-8', errors='ignore')
                                
                                for pattern in patterns:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        found = True
                                        break
                                
                                if found:
                                    break
                        except Exception:
                            continue
                
                if found:
                    detected_technologies[category].append(tech_name)
        
        # Remove empty categories
        return {k: v for k, v in detected_technologies.items() if v}
    
    @abstractmethod
    def _calculate_expected_count(self, total_loc: int, file_count: int,
                                lang_files: List[FileAnalysis]) -> int:
        """Calculate expected count for this gate"""
        pass
    
    @abstractmethod
    def _assess_implementation_quality(self, matches: List[Dict[str, Any]]) -> Dict[str, float]:
        """Assess implementation quality"""
        pass
    
    @abstractmethod
    def _get_zero_implementation_recommendations(self) -> List[str]:
        """Get recommendations when no implementation found"""
        pass
    
    @abstractmethod
    def _get_partial_implementation_recommendations(self) -> List[str]:
        """Get recommendations for partial implementation"""
        pass
    
    @abstractmethod
    def _get_quality_improvement_recommendations(self) -> List[str]:
        """Get recommendations for quality improvement"""
        pass
    
    def _get_file_extensions(self) -> List[str]:
        """Get file extensions for the current language"""
        
        if self.language == Language.PYTHON:
            return ['*.py']
        elif self.language == Language.JAVA:
            return ['*.java']
        elif self.language == Language.JAVASCRIPT:
            return ['*.js', '*.mjs']
        elif self.language == Language.TYPESCRIPT:
            return ['*.ts', '*.tsx']
        elif self.language == Language.CSHARP:
            return ['*.cs']
        else:
            return ['*.*']
    
    def _search_files_for_patterns(self, target_path: Path, extensions: List[str], 
                                 patterns: List[str]) -> List[Dict[str, Any]]:
        """Search files for patterns"""
        
        matches = []
        
        for extension in extensions:
            for file_path in target_path.rglob(extension):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        lines = content.split('\n')
                        
                        for line_num, line in enumerate(lines, 1):
                            for pattern in patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    matches.append({
                                        'file': str(file_path),
                                        'line': line_num,
                                        'match': line.strip(),
                                        'pattern': pattern
                                    })
                    except Exception:
                        continue
        
        return matches
    
    def _estimate_expected_count(self, file_analyses: List[FileAnalysis]) -> int:
        """Estimate expected count based on file analyses"""
        
        # Filter files for current language
        lang_files = [f for f in file_analyses if f.language == self.language]
        
        if not lang_files:
            return 0
        
        total_loc = sum(f.lines_of_code for f in lang_files)
        file_count = len(lang_files)
        
        return self._calculate_expected_count(total_loc, file_count, lang_files)
    
    def _calculate_quality_score(self, matches: List[Dict[str, Any]], expected: int) -> float:
        """Calculate quality score based on matches and expected count"""
        
        if expected == 0:
            return 100.0 if len(matches) == 0 else 0.0
        
        if not matches:
            return 0.0
        
        # Base coverage score
        coverage = min(len(matches) / expected, 1.0) * 100
        
        # Quality bonuses from implementation assessment
        try:
            quality_bonuses = self._assess_implementation_quality(matches)
            quality_bonus = sum(quality_bonuses.values()) if quality_bonuses else 0
        except Exception as e:
            print(f"⚠️ Quality assessment failed: {e}")
            quality_bonus = 0
        
        # Final quality score (coverage weighted 70%, quality bonus 30%)
        final_score = (coverage * 0.7) + min(quality_bonus, 30)
        
        # Ensure score is always a valid float between 0 and 100
        result = max(0.0, min(final_score, 100.0))
        
        return result 