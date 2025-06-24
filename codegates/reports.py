"""
Report Generator - Creates validation reports in multiple formats
Uses the same exact logic as VS Code extension for consistency
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import ValidationResult, ReportConfig


class SharedReportGenerator:
    """Shared report generation logic used by both VS Code extension and HTML generator"""
    
    @staticmethod
    def transform_result_to_extension_format(result: ValidationResult) -> Dict[str, Any]:
        """Transform ValidationResult to the same format used by VS Code extension"""
        # Convert ValidationResult gate statuses to match API format
        gates = []
        for gate_score in result.gate_scores:
            # Map status to match VS Code extension format exactly
            if gate_score.status == "PASSED":
                status = "PASS"
            elif gate_score.status == "FAILED":
                status = "FAIL"
            elif gate_score.status == "WARNING":
                status = "WARNING"
            elif gate_score.status == "NOT_APPLICABLE":
                status = "NOT_APPLICABLE"
            else:
                # For any other status, map based on score
                if gate_score.final_score >= 80:
                    status = "PASS"
                elif gate_score.final_score >= 60:
                    status = "WARNING"
                else:
                    status = "FAIL"
            
            gates.append({
                "name": gate_score.gate.value,
                "status": status,
                "score": gate_score.final_score,
                "details": gate_score.details,
                "expected": gate_score.expected,
                "found": gate_score.found,
                "coverage": gate_score.coverage,
                "quality_score": gate_score.quality_score
            })
        
        # Return in the exact same format as VS Code extension expects
        return {
            "gates": gates,
            "score": result.overall_score,
            "languages_detected": [lang.value for lang in result.languages] if hasattr(result, 'languages') and result.languages else [],
            "repository_url": getattr(result, 'repository_url', None),
            "project_name": result.project_name
        }
    
    @staticmethod
    def calculate_summary_stats(result_data: Dict[str, Any]) -> Dict[str, int]:
        """Calculate summary statistics - exact same logic as VS Code extension"""
        gates = result_data.get("gates", [])
        return {
            "total_gates": len(gates),
            "implemented_gates": len([g for g in gates if g.get("status") == 'PASS']),
            "partial_gates": len([g for g in gates if g.get("status") == 'WARNING']),
            "not_implemented_gates": len([g for g in gates if g.get("status") == 'FAIL']),
            "not_applicable_gates": len([g for g in gates if g.get("status") == 'NOT_APPLICABLE'])
        }
    
    @staticmethod
    def extract_project_name(result_data: Dict[str, Any]) -> str:
        """Extract project name - exact same logic as VS Code extension"""
        project_name = 'Repository Scan Results'
        if result_data.get('repository_url'):
            url_parts = result_data['repository_url'].split('/')
            project_name = url_parts[-1] or project_name
            if project_name.endswith('.git'):
                project_name = project_name[:-4]
        elif result_data.get('project_name'):
            project_name = result_data['project_name']
        return project_name
    
    @staticmethod
    def generate_tech_stack(result_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate technology stack - exact same logic as VS Code extension"""
        tech_stack = []
        if result_data.get('languages_detected'):
            for lang in result_data['languages_detected']:
                tech_stack.append({
                    'type': 'Languages',
                    'name': lang.capitalize(),
                    'version': 'N/A',
                    'purpose': 'detected'
                })
        return tech_stack
    
    @staticmethod
    def analyze_secrets(result_data: Dict[str, Any]) -> Dict[str, str]:
        """Analyze secrets - exact same logic as VS Code extension"""
        gates = result_data.get("gates", [])
        secrets_gate = next((g for g in gates if g.get("name") == 'avoid_logging_secrets'), None)
        
        if secrets_gate:
            if secrets_gate.get("status") == 'PASS':
                return {
                    'status': 'safe',
                    'message': 'No secrets or confidential data detected'
                }
            elif secrets_gate.get("found", 0) > 0:
                return {
                    'status': 'warning',
                    'message': f'Found {secrets_gate["found"]} potential confidential data logging violations'
                }
        
        return {
            'status': 'unknown',
            'message': 'Secrets analysis not available'
        }
    
    @staticmethod
    def get_gate_categories() -> Dict[str, List[str]]:
        """Get gate categories - exact same as VS Code extension"""
        return {
            'Auditability': ['structured_logs', 'avoid_logging_secrets', 'audit_trail', 'correlation_id', 'api_logs', 'background_jobs', 'ui_errors'],
            'Availability': ['retry_logic', 'timeouts', 'throttling', 'circuit_breakers'],
            'Error Handling': ['error_logs', 'http_codes', 'ui_error_tools'],
            'Testing': ['automated_tests']
        }
    
    @staticmethod
    def get_gate_name_map() -> Dict[str, str]:
        """Get gate name mapping - exact same as VS Code extension"""
        return {
            'structured_logs': 'Logs Searchable Available',
            'avoid_logging_secrets': 'Avoid Logging Confidential Data',
            'audit_trail': 'Create Audit Trail Logs',
            'correlation_id': 'Tracking ID For Log Messages',
            'api_logs': 'Log Rest API Calls',
            'background_jobs': 'Log Application Messages',
            'ui_errors': 'Client UI Errors Logged',
            'retry_logic': 'Retry Logic',
            'timeouts': 'Set Timeouts IO Operations',
            'throttling': 'Throttling Drop Request',
            'circuit_breakers': 'Circuit Breakers Outgoing Requests',
            'error_logs': 'Log System Errors',
            'http_codes': 'Use HTTP Standard Error Codes',
            'ui_error_tools': 'Include Client Error Tracking',
            'automated_tests': 'Automated Regression Testing'
        }
    
    @staticmethod
    def format_gate_name(name: str) -> str:
        """Format gate name - exact same logic as VS Code extension"""
        gate_name_map = SharedReportGenerator.get_gate_name_map()
        return gate_name_map.get(name, name.split('_').map(lambda word: word.capitalize()).join(' '))
    
    @staticmethod
    def get_status_info(status: str) -> Dict[str, str]:
        """Get status info - exact same logic as VS Code extension"""
        if status == 'PASS':
            return {'class': 'implemented', 'text': '✓ Implemented'}
        elif status == 'WARNING':
            return {'class': 'partial', 'text': '⚬ Partial'}
        elif status == 'NOT_APPLICABLE':
            return {'class': 'partial', 'text': 'N/A'}
        else:
            return {'class': 'not-implemented', 'text': '✗ Missing'}
    
    @staticmethod
    def format_evidence(gate: Dict[str, Any]) -> str:
        """Format evidence - exact same logic as VS Code extension"""
        if gate.get("status") == 'NOT_APPLICABLE':
            return 'Not applicable to this project type'
        
        details = gate.get("details", [])
        if not details or len(details) == 0:
            return 'No relevant patterns found in codebase'
        
        # Process details to avoid duplication (same logic as VS Code extension)
        processed_details = []
        seen_content = set()
        
        for detail in details[:3]:  # First 3 details
            # Skip if we've seen this content before (avoid duplicates)
            clean_detail = str(detail).strip().lower()
            if clean_detail not in seen_content and len(str(detail)) > 5:
                seen_content.add(clean_detail)
                processed_details.append(str(detail))
        
        # If we have basic statistics, show them first
        evidence = ''
        found = gate.get("found")
        expected = gate.get("expected")
        coverage = gate.get("coverage")
        
        if found is not None and expected is not None and coverage is not None:
            if found > 0:
                evidence = f"Found {found} implementations with {coverage:.1f}% coverage"
            else:
                evidence = 'No relevant patterns found in codebase'
        
        # Add processed details if they provide additional value
        if processed_details:
            # Check if details provide more than just the basic "no patterns found" message
            meaningful_details = [detail for detail in processed_details if 
                not detail.lower().startswith('no') and 
                'not found' not in detail.lower() and
                len(detail) > 20  # Filter out very short, likely redundant details
            ]
            
            if meaningful_details:
                if evidence:
                    evidence += '<br>' + '<br>'.join(meaningful_details)
                else:
                    evidence = '<br>'.join(meaningful_details)
            elif not evidence:
                # Fall back to the first detail if no meaningful details and no basic stats
                evidence = processed_details[0] if processed_details else 'No relevant patterns found in codebase'
        elif not evidence:
            # Final fallback
            evidence = 'No relevant patterns found in codebase'
        
        return evidence
    
    @staticmethod
    def get_recommendation(gate: Dict[str, Any], gate_name: str) -> str:
        """Get recommendation - exact same logic as VS Code extension"""
        status = gate.get("status")
        
        if status == 'PASS':
            return 'Continue maintaining good practices'
        elif status == 'WARNING':
            return f"Expand implementation of {gate_name.lower()}"
        elif status == 'NOT_APPLICABLE':
            return 'Not applicable to this project type'
        else:
            return f"Implement {gate_name.lower()}"


class ReportGenerator:
    """Generates validation reports in multiple formats using shared logic"""
    
    def __init__(self, config: ReportConfig):
        self.config = config
        
    def generate(self, result: ValidationResult) -> List[str]:
        """Generate reports in specified format(s)"""
        
        output_dir = Path(self.config.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = []
        
        if self.config.format in ['json', 'all']:
            json_file = self._generate_json_report(result, output_dir)
            generated_files.append(json_file)
        
        if self.config.format in ['html', 'all']:
            html_file = self._generate_html_report(result, output_dir)
            generated_files.append(html_file)
        
        return generated_files
    
    def _generate_json_report(self, result: ValidationResult, output_dir: Path) -> str:
        """Generate JSON report"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"codegates_report_{timestamp}.json"
        filepath = output_dir / filename
        
        # Use shared logic to transform result
        result_data = SharedReportGenerator.transform_result_to_extension_format(result)
        
        # Convert result to dict for JSON serialization
        report_data = {
            "project_name": result.project_name,
            "project_path": result.project_path,
            "language": result.language.value if hasattr(result, 'language') else 'unknown',
            "scan_date": result.timestamp.isoformat() if hasattr(result, 'timestamp') else datetime.now().isoformat(),
            "scan_duration": getattr(result, 'scan_duration', 0),
            "overall_score": result.overall_score,
            "total_files": getattr(result, 'total_files', 0),
            "total_lines": getattr(result, 'total_lines', 0),
            "gate_summary": SharedReportGenerator.calculate_summary_stats(result_data),
            "gates": result_data["gates"],
            "critical_issues": getattr(result, 'critical_issues', []),
            "recommendations": getattr(result, 'recommendations', [])
        }
        
        with open(filepath, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        return str(filepath)
    
    def _generate_html_report(self, result: ValidationResult, output_dir: Path) -> str:
        """Generate HTML report with modern styling"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"codegates_report_{timestamp}.html"
        filepath = output_dir / filename
        
        html_content = self._generate_html_content(result)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(filepath)
    
    def _generate_html_content(self, result: ValidationResult) -> str:
        """Generate HTML content using exact same logic as VS Code extension"""
        
        # Transform result using shared logic
        result_data = SharedReportGenerator.transform_result_to_extension_format(result)
        
        # Calculate summary statistics using shared logic
        stats = SharedReportGenerator.calculate_summary_stats(result_data)
        
        # Extract project name using shared logic
        project_name = SharedReportGenerator.extract_project_name(result_data)
        
        # Get current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Generate technology stack using shared logic
        tech_stack = SharedReportGenerator.generate_tech_stack(result_data)
        
        # Analyze secrets using shared logic
        secrets_analysis = SharedReportGenerator.analyze_secrets(result_data)
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hard Gate Assessment - {project_name}</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="report-container">
        <h1>{project_name}</h1>
        <p style="color: #2563eb; margin-bottom: 30px; font-weight: 500;">Hard Gate Assessment Report</p>
        
        <h2>Executive Summary</h2>
        
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-number">{stats['total_gates']}</div>
                <div class="stat-label">Total Gates Evaluated</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['implemented_gates']}</div>
                <div class="stat-label">Gates Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['partial_gates']}</div>
                <div class="stat-label">Partially Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['not_implemented_gates']}</div>
                <div class="stat-label">Not Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['not_applicable_gates']}</div>
                <div class="stat-label">Not Applicable</div>
            </div>
        </div>
        
        <h3>Overall Compliance</h3>
        <div class="compliance-bar">
            <div class="compliance-fill" style="width: {result_data['score']:.1f}%"></div>
        </div>
        <p><strong>{result_data['score']:.1f}% Hard Gates Compliance</strong></p>
        
        {self._generate_technology_section_html(tech_stack)}
        
        {self._generate_secrets_section_html(secrets_analysis)}
        
        {self._generate_gates_section_html(result_data)}
        
        <footer style="margin-top: 50px; text-align: center; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            <p>Hard Gate Assessment Report generated on {timestamp}</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_template
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML report"""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f3f4f6;
        }
        
        h1 {
            font-size: 2em;
            color: #1f2937;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }
        
        h2 {
            color: #1f2937;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
            margin-top: 40px;
        }
        
        h3 {
            color: #374151;
            margin-top: 30px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }
        
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        th {
            background: #2563eb;
            color: #fff;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        tr:hover {
            background: #f9fafb;
        }
        
        .status-implemented {
            color: #059669;
            background: #ecfdf5;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .status-partial {
            color: #d97706;
            background: #fffbeb;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .status-not-implemented {
            color: #dc2626;
            background: #fef2f2;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .stat-card {
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            text-align: center;
        }
        
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #2563eb;
        }
        
        .stat-label {
            color: #6b7280;
            margin-top: 5px;
        }
        
        .compliance-bar {
            width: 100%;
            height: 20px;
            background: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .compliance-fill {
            height: 100%;
            background: linear-gradient(90deg, #dc2626 0%, #d97706 50%, #059669 100%);
            transition: width 0.3s ease;
        }
        
        .secrets-safe {
            color: #059669;
            background: #ecfdf5;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #059669;
            margin: 10px 0;
        }
        
        .secrets-warning {
            color: #d97706;
            background: #fffbeb;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #d97706;
            margin: 10px 0;
        }
        
        .secrets-unknown {
            color: #6b7280;
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #6b7280;
            margin: 10px 0;
        }
        """
    
    def _generate_technology_section_html(self, tech_stack: List[Dict[str, str]]) -> str:
        """Generate technology section HTML using shared logic"""
        if not tech_stack:
            return ""
        
        rows = ""
        for tech in tech_stack:
            rows += f"""
                        <tr>
                            <td><strong>{tech['type']}</strong></td>
                            <td>{tech['name']}</td>
                            <td>{tech['version']}</td>
                            <td>{tech['purpose']}</td>
                        </tr>"""
        
        return f"""
        <div class="technology-stack">
            <h2>Technology Stack</h2>
            <table class="tech-table">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Name</th>
                        <th>Version</th>
                        <th>Purpose</th>
                    </tr>
                </thead>
                <tbody>{rows}
                </tbody>
            </table>
        </div>"""
    
    def _generate_secrets_section_html(self, secrets_analysis: Dict[str, str]) -> str:
        """Generate secrets section HTML using shared logic"""
        if secrets_analysis['status'] == 'safe':
            return f"""
        <div class="secrets-analysis">
            <h2>Secrets Analysis</h2>
            <p class="secrets-safe">
                <strong>✅ {secrets_analysis['message']}</strong> in the analyzed codebase.
            </p>
        </div>"""
        elif secrets_analysis['status'] == 'warning':
            return f"""
        <div class="secrets-analysis">
            <h2>Secrets Analysis</h2>
            <p class="secrets-warning">
                <strong>⚠️ {secrets_analysis['message']}</strong>
            </p>
        </div>"""
        else:
            return f"""
        <div class="secrets-analysis">
            <h2>Secrets Analysis</h2>
            <p class="secrets-unknown">
                <strong>ℹ️ {secrets_analysis['message']}</strong>
            </p>
        </div>"""
    
    def _generate_gates_section_html(self, result_data: Dict[str, Any]) -> str:
        """Generate gates section HTML using shared logic"""
        gates = result_data.get("gates", [])
        gate_categories = SharedReportGenerator.get_gate_categories()
        
        sections = ""
        
        for category_name, gate_names in gate_categories.items():
            category_gates = [g for g in gates if g.get("name") in gate_names]
            
            if not category_gates:
                continue
            
            rows = ""
            for gate in category_gates:
                gate_name = SharedReportGenerator.format_gate_name(gate.get("name", ""))
                status_info = SharedReportGenerator.get_status_info(gate.get("status", ""))
                evidence = SharedReportGenerator.format_evidence(gate)
                recommendation = SharedReportGenerator.get_recommendation(gate, gate_name)
                
                rows += f"""
                        <tr>
                            <td><strong>{gate_name}</strong></td>
                            <td><span class="status-{status_info['class']}">{status_info['text']}</span></td>
                            <td>{evidence}</td>
                            <td>{recommendation}</td>
                        </tr>"""
            
            if rows:
                sections += f"""
            <div class="gate-category">
                <h3>{category_name}</h3>
                <table class="gates-table">
                    <thead>
                        <tr>
                            <th>Practice</th>
                            <th>Status</th>
                            <th>Evidence</th>
                            <th>Recommendation</th>
                        </tr>
                    </thead>
                    <tbody>{rows}
                    </tbody>
                </table>
            </div>"""
        
        if sections:
            return f"""
        <div class="gates-analysis">
            <h2>Hard Gates Analysis</h2>
            {sections}
        </div>"""
        else:
            return "" 