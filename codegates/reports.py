"""
Report Generator - Creates validation reports in multiple formats
"""

import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import ValidationResult, ReportConfig


class ReportGenerator:
    """Generates validation reports in multiple formats"""
    
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
        
        # Convert result to dict for JSON serialization
        report_data = {
            "project_name": result.project_name,
            "project_path": result.project_path,
            "language": result.language.value,
            "scan_date": result.timestamp.isoformat(),
            "scan_duration": result.scan_duration,
            "overall_score": result.overall_score,
            "total_files": result.total_files,
            "total_lines": result.total_lines,
            "gate_summary": {
                "passed": result.passed_gates,
                "warning": result.warning_gates,
                "failed": result.failed_gates
            },
            "gate_scores": [
                {
                    "gate": gate.gate.value,
                    "expected": gate.expected,
                    "found": gate.found,
                    "coverage": gate.coverage,
                    "quality_score": gate.quality_score,
                    "final_score": gate.final_score,
                    "status": gate.status,
                    "details": gate.details if self.config.include_details else [],
                    "recommendations": gate.recommendations if self.config.include_recommendations else []
                }
                for gate in result.gate_scores
            ],
            "critical_issues": result.critical_issues,
            "recommendations": result.recommendations if self.config.include_recommendations else []
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
        """Generate the HTML content with modern theme"""
        
        # Calculate statistics
        total_gates = len(result.gate_scores)
        passed_gates = len([g for g in result.gate_scores if g.status == 'PASSED'])
        warning_gates = len([g for g in result.gate_scores if g.status == 'WARNING'])
        failed_gates = len([g for g in result.gate_scores if g.status == 'FAILED'])
        
        compliance_percentage = (passed_gates / total_gates * 100) if total_gates > 0 else 0
        
        # Get project name
        project_name = result.project_name or "Unknown Project"
        
        # Generate technology stack
        technologies_html = self._generate_technologies_section(result)
        
        # Generate secrets analysis
        secrets_html = self._generate_secrets_section(result)
        
        # Generate hard gates analysis
        gates_html = self._generate_gates_analysis(result)
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hard Gate Assessment - {project_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f3f4f6;
        }}
        
        h1 {{
            font-size: 2em;
            color: #1f2937;
            border-bottom: 3px solid #2563eb;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        
        h2 {{
            color: #1f2937;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
            margin-top: 40px;
        }}
        
        h3 {{
            color: #374151;
            margin-top: 30px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            border: 1px solid #e5e7eb;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        th {{
            background: #2563eb;
            color: #fff;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        tr:hover {{
            background: #f9fafb;
        }}
        
        .status-implemented {{
            color: #059669;
            background: #ecfdf5;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }}
        
        .status-partial {{
            color: #d97706;
            background: #fffbeb;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }}
        
        .status-not-implemented {{
            color: #dc2626;
            background: #fef2f2;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }}
        
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #2563eb;
        }}
        
        .stat-label {{
            color: #6b7280;
            margin-top: 5px;
        }}
        
        .compliance-bar {{
            width: 100%;
            height: 20px;
            background: #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }}
        
        .compliance-fill {{
            height: 100%;
            background: linear-gradient(90deg, #dc2626 0%, #d97706 50%, #059669 100%);
            transition: width 0.3s ease;
        }}
        
        .success-message {{
            color: #059669;
            background: #ecfdf5;
            padding: 10px;
            border-radius: 4px;
            border-left: 4px solid #059669;
        }}
        
        .warning-message {{
            color: #d97706;
            background: #fffbeb;
            padding: 10px;
            border-radius: 4px;
            border-left: 4px solid #d97706;
        }}
        
        .error-message {{
            color: #dc2626;
            background: #fef2f2;
            padding: 10px;
            border-radius: 4px;
            border-left: 4px solid #dc2626;
        }}
        
        .confidence-score {{
            color: #6b7280;
            font-size: 0.9em;
        }}
        
        .pattern-details {{
            color: #6b7280;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>{project_name}</h1>
    <p style="color: #2563eb; margin-bottom: 30px; font-weight: 500;">Hard Gate Assessment Report</p>
    
    <h2>Executive Summary</h2>
    
    <div class="summary-stats">
        <div class="stat-card">
            <div class="stat-number">{total_gates}</div>
            <div class="stat-label">Total Gates Evaluated</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{passed_gates}</div>
            <div class="stat-label">Gates Met</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{warning_gates}</div>
            <div class="stat-label">Partially Met</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{failed_gates}</div>
            <div class="stat-label">Not Met</div>
        </div>
    </div>
    
    <h3>Overall Compliance</h3>
    <div class="compliance-bar">
        <div class="compliance-fill" style="width: {compliance_percentage:.1f}%"></div>
    </div>
    <p><strong>{compliance_percentage:.1f}% Hard Gates Compliance</strong></p>

    {technologies_html}

    {secrets_html}

    {gates_html}

    <footer style="margin-top: 50px; text-align: center; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 20px;">
        <p>Hard Gate Assessment Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </footer>
</body>
</html>"""
        
        return html_template
    
    def _generate_technologies_section(self, result: ValidationResult) -> str:
        """Generate technology stack section"""
        if not hasattr(result, 'technologies') or not result.technologies:
            return ""
        
        technologies = result.technologies
        rows = []
        
        # Group technologies by type
        tech_groups = {}
        for tech in technologies:
            tech_type = tech.get('type', 'Unknown')
            if tech_type not in tech_groups:
                tech_groups[tech_type] = []
            tech_groups[tech_type].append(tech)
        
        for tech_type, techs in tech_groups.items():
            for tech in techs:
                name = tech.get('name', 'Unknown')
                version = tech.get('version', 'N/A')
                purpose = tech.get('purpose', 'detected by LLM')
                
                rows.append(f"""
            <tr>
                <td><strong>{tech_type.title()}</strong></td>
                <td>{name}</td>
                <td>{version}</td>
                <td>{purpose}</td>
            </tr>""")
        
        if not rows:
            return ""
        
        return f"""
    <h2>Technology Stack</h2>
    <table>
        <thead>
        <tr>
                <th>Type</th>
                <th>Name</th>
                <th>Version</th>
                <th>Purpose</th>
        </tr>
        </thead>
        <tbody>
{''.join(rows)}
        </tbody>
    </table>"""
    
    def _generate_secrets_section(self, result: ValidationResult) -> str:
        """Generate secrets analysis section"""
        # Check if any secrets were found
        secrets_found = False
        for gate in result.gate_scores:
            if gate.gate == 'avoid_logging_secrets' and gate.status == 'FAILED':
                secrets_found = True
                break
        
        if secrets_found:
            return """
    <h2>Secrets Analysis</h2>
    <p class="error-message">
        <strong>⚠️ Potential secrets or confidential data detected</strong> in the analyzed codebase. Please review and remediate.
    </p>"""
        else:
            return """
    <h2>Secrets Analysis</h2>
    <p class="success-message">
        <strong>✅ No secrets or confidential data detected</strong> in the analyzed codebase.
    </p>"""
    
    def _generate_gates_analysis(self, result: ValidationResult) -> str:
        """Generate hard gates analysis section"""
        # Group gates by category
        gate_categories = {
            'Auditability': [
                'structured_logs',
                'avoid_logging_secrets', 
                'audit_trail',
                'correlation_id',
                'api_logs',
                'background_jobs',
                'ui_errors'
            ],
            'Availability': [
                'retry_logic',
                'timeouts',
                'throttling',
                'circuit_breakers'
            ],
            'Error Handling': [
                'error_logs',
                'http_codes',
                'ui_error_tools'
            ],
            'Testing': [
                'automated_tests'
            ]
        }
        
        sections = []
        
        for category, gate_names in gate_categories.items():
            category_gates = [g for g in result.gate_scores if g.gate in gate_names]
            if not category_gates:
                continue
            
            rows = []
            for gate in category_gates:
                practice_name = self._format_gate_name(gate.gate)
                status_class, status_text = self._get_status_display(gate.status)
                evidence = self._format_evidence(gate)
                recommendation = self._format_recommendation(gate)
                
                rows.append(f"""
            <tr>
                <td><strong>{practice_name}</strong></td>
                <td><span class="{status_class}">{status_text}</span></td>
                <td>{evidence}</td>
                <td>{recommendation}</td>
            </tr>""")
            
            if rows:
                sections.append(f"""
    <h3>{category}</h3>
    <table>
        <thead>
            <tr>
                <th>Practice</th>
                <th>Status</th>
                <th>Evidence</th>
                <th>Recommendation</th>
        </tr>
        </thead>
        <tbody>
{''.join(rows)}
        </tbody>
    </table>""")
        
        if sections:
            return f"""
    <h2>Hard Gates Analysis</h2>
{''.join(sections)}"""
        else:
            return ""
    
    def _format_gate_name(self, gate_name: str) -> str:
        """Format gate name for display"""
        name_mapping = {
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
        return name_mapping.get(gate_name, gate_name.replace('_', ' ').title())
    
    def _get_status_display(self, status: str) -> tuple:
        """Get status display class and text"""
        if status == 'PASSED':
            return 'status-implemented', '✓ Implemented'
        elif status == 'WARNING':
            return 'status-partial', '⚠ Partial'
        else:
            return 'status-not-implemented', '✗ Missing'
    
    def _format_evidence(self, gate) -> str:
        """Format evidence for display"""
        if not hasattr(gate, 'details') or not gate.details:
            if gate.status == 'FAILED':
                return "No relevant patterns found in codebase"
            else:
                return "Implementation detected"
        
        evidence_parts = []
        for detail in gate.details[:3]:  # Show first 3 details
            evidence_parts.append(detail)
        
        # Add confidence score if available
        if hasattr(gate, 'confidence') and gate.confidence:
            confidence_text = f"<br><small class='confidence-score'>🎯 <strong>Confidence: {gate.confidence}%</strong></small>"
            evidence_parts.append(confidence_text)
        
        return "<br>".join(evidence_parts)
    
    def _format_recommendation(self, gate) -> str:
        """Format recommendation for display"""
        if hasattr(gate, 'recommendations') and gate.recommendations:
            return gate.recommendations[0]  # Show first recommendation
        elif gate.status == 'PASSED':
            return "Continue maintaining good practices"
        elif gate.status == 'WARNING':
            return "Review and improve implementation"
        else:
            practice_name = self._format_gate_name(gate.gate).lower()
            return f"Implement {practice_name}" 