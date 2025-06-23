# CodeGates VS Code Extension

🛡️ **Real-time hard gate validation and code quality analysis for production-ready development**

The CodeGates VS Code extension brings the power of enterprise-grade hard gate validation directly into your editor, providing real-time feedback on code quality, security, and production readiness.

## ✨ Features

### 🔍 **Real-Time Analysis**
- **Workspace Scanning**: Complete project analysis with comprehensive reporting
- **File-Level Scanning**: Quick validation of individual files
- **Auto-Scan on Save**: Optional automatic scanning when files are modified
- **Live Diagnostics**: Inline warnings and errors in the editor

### 🤖 **LLM-Enhanced Analysis**
- **AI-Powered Insights**: Leverage OpenAI, Anthropic, Gemini, or local models
- **Context-Aware Recommendations**: Technology-specific suggestions
- **Security Vulnerability Detection**: AI-powered threat identification
- **Code Quality Assessment**: Intelligent analysis beyond pattern matching

### 📊 **Rich UI Integration**
- **Activity Bar Panel**: Dedicated CodeGates sidebar with multiple views
- **Overview Dashboard**: Visual summary of gate validation results
- **Issues Tree**: Hierarchical view of problems by gate and severity
- **Recommendations Panel**: Actionable improvement suggestions
- **Hard Gates Reference**: Interactive guide to all 15 validation gates

### ⚙️ **Flexible Configuration**
- **Customizable Thresholds**: Set quality standards for your team
- **Language Selection**: Choose which languages to analyze
- **Exclude Patterns**: Skip test files, dependencies, or other directories
- **LLM Provider Options**: Support for multiple AI providers
- **Report Formats**: Generate HTML, JSON, or both

## 🚀 Quick Start

### Installation

1. **Install from VS Code Marketplace** (coming soon)
   ```
   ext install codegates.codegates
   ```

2. **Or install from VSIX**
   - Download the `.vsix` file
   - Run: `code --install-extension codegates-1.0.0.vsix`

### Setup

1. **Configure CodeGates Path**
   - Open VS Code Settings (`Ctrl+,`)
   - Search for "CodeGates"
   - Set the path to your CodeGates installation

2. **Optional: Enable LLM Analysis**
   - Use Command Palette (`Ctrl+Shift+P`)
   - Run: `CodeGates: Enable LLM Analysis`
   - Select your preferred provider and configure API keys

### First Scan

1. **Open a Project**
   - Open any Python, Java, JavaScript, TypeScript, or C# project

2. **Run Analysis**
   - Click the CodeGates icon in the Activity Bar
   - Click "Scan Workspace" or use `Ctrl+Shift+P` → `CodeGates: Scan Workspace`

3. **View Results**
   - Check the Overview panel for overall score
   - Browse issues by gate in the Issues panel
   - Review recommendations for improvements

## 📋 Commands

| Command | Description | Shortcut |
|---------|-------------|----------|
| `CodeGates: Scan Workspace` | Analyze entire workspace | - |
| `CodeGates: Scan Current File` | Analyze active file | - |
| `CodeGates: Show Report` | Open latest HTML report | - |
| `CodeGates: Configure Settings` | Open CodeGates settings | - |
| `CodeGates: Enable LLM Analysis` | Setup AI-powered analysis | - |
| `CodeGates: View Hard Gates` | Show gates reference | - |
| `CodeGates: Refresh Results` | Re-run last analysis | - |

## ⚙️ Configuration

### Basic Settings

```json
{
  "codegates.enabled": true,
  "codegates.autoScan": false,
  "codegates.scanOnOpen": true,
  "codegates.threshold": 70,
  "codegates.languages": ["python", "java", "javascript", "typescript", "csharp"],
  "codegates.excludePatterns": ["node_modules/**", ".git/**", "**/__pycache__/**"]
}
```

### LLM Configuration

```json
{
  "codegates.llm.enabled": true,
  "codegates.llm.provider": "openai",
  "codegates.llm.model": "gpt-4",
  "codegates.llm.temperature": 0.1
}
```

### Report Settings

```json
{
  "codegates.reports.format": "html",
  "codegates.reports.autoOpen": true,
  "codegates.notifications.level": "info"
}
```

## 🛡️ Hard Gates Overview

The extension validates 15 production-critical hard gates:

| Gate | Weight | Description |
|------|--------|-------------|
| **Structured Logs** | 2.0 | JSON-formatted logging with consistent fields |
| **Avoid Logging Secrets** | 2.0 | Prevents sensitive data in log files |
| **Audit Trail** | 1.8 | Tracks critical business operations |
| **Error Logs** | 1.8 | Comprehensive exception handling |
| **Circuit Breakers** | 1.7 | Fault tolerance for external services |
| **Timeouts** | 1.6 | Prevents hanging operations |
| **UI Errors** | 1.5 | User-friendly error handling |
| **Correlation ID** | 1.5 | Request tracing across services |
| **Automated Tests** | 1.5 | Test coverage and quality |
| **UI Error Tools** | 1.4 | Error monitoring integration |
| **Retry Logic** | 1.4 | Resilient failure handling |
| **API Logs** | 1.3 | Endpoint access logging |
| **Throttling** | 1.3 | Rate limiting implementation |
| **Background Jobs** | 1.2 | Async task monitoring |
| **HTTP Codes** | 1.2 | Proper status code usage |

## 🔧 Advanced Usage

### Context Menu Integration

- **Right-click files**: Scan individual files
- **Right-click folders**: Scan specific directories
- **Explorer integration**: Quick access to CodeGates commands

### Status Bar Integration

- **Live Status**: Current scan status and overall score
- **Quick Actions**: Click for instant workspace scan
- **Progress Indicators**: Visual feedback during analysis

### Problem Panel Integration

- **Inline Diagnostics**: Issues appear directly in code
- **Problem Panel**: Centralized view of all CodeGates issues
- **Quick Fixes**: Jump to problematic code sections

## 🤖 LLM Providers

### Supported Providers

| Provider | Models | Setup Required |
|----------|--------|----------------|
| **OpenAI** | GPT-4, GPT-3.5-turbo | API Key |
| **Anthropic** | Claude-3-Sonnet, Claude-3-Haiku | API Key |
| **Google** | Gemini-Pro | API Key |
| **Ollama** | Llama2, CodeLlama, Mistral | Local Installation |
| **Local** | Custom OpenAI-compatible APIs | Endpoint URL |

### API Key Configuration

Set API keys via environment variables or VS Code settings:

```bash
# Environment variables
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
```

Or in VS Code settings:
```json
{
  "codegates.llm.apiKey": "your-key"
}
```

## 📊 Reports

### HTML Reports
- **Interactive dashboards** with filtering and sorting
- **Visual charts** showing gate performance over time
- **Detailed recommendations** with code examples
- **Technology-specific insights** based on detected frameworks

### JSON Reports
- **Machine-readable format** for CI/CD integration
- **Programmatic analysis** of results
- **Historical comparison** capabilities
- **Custom tooling integration**

## 🔍 Troubleshooting

### Common Issues

1. **Extension Not Activating**
   - Ensure supported language files are open
   - Check VS Code version compatibility (1.80.0+)

2. **CodeGates Not Found**
   - Set correct path in settings: `codegates.codegatePath`
   - Verify Python installation: `codegates.pythonPath`

3. **LLM Analysis Failing**
   - Check API key configuration
   - Verify network connectivity
   - Review provider-specific requirements

4. **No Results Showing**
   - Check output panel for error messages
   - Verify workspace contains supported file types
   - Review exclude patterns in settings

### Debug Mode

Enable verbose logging:
```json
{
  "codegates.notifications.level": "verbose"
}
```

Check VS Code Output panel → CodeGates for detailed logs.

## 🤝 Contributing

### Development Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/codegates
   cd codegates/vscode-extension
   ```

2. **Install Dependencies**
   ```bash
   npm install
   ```

3. **Build Extension**
   ```bash
   npm run compile
   ```

4. **Run in Development**
   - Open in VS Code
   - Press `F5` to launch Extension Development Host

### Building VSIX

```bash
npm run package
```

## 📄 License

MIT License - see [LICENSE](../LICENSE) file for details.

## 🆘 Support

- 📧 **Email**: support@codegates.dev
- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/codegates/issues)
- 📖 **Documentation**: [CodeGates Docs](https://codegates.dev/docs)

---

**CodeGates VS Code Extension** - Bringing enterprise-grade code quality validation directly to your development workflow. 