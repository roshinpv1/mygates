"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const apiRunner_1 = require("./runners/apiRunner");
const configurationManager_1 = require("./utils/configurationManager");
const notificationManager_1 = require("./utils/notificationManager");
class CodeGatesScanPanel {
    static createOrShow(extensionUri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;
        if (CodeGatesScanPanel.currentPanel) {
            CodeGatesScanPanel.currentPanel.panel.reveal(column);
            return;
        }
        const panel = vscode.window.createWebviewPanel('codegatesScan', 'CodeGates Repository Scan', column || vscode.ViewColumn.One, {
            enableScripts: true,
            retainContextWhenHidden: true
        });
        CodeGatesScanPanel.currentPanel = new CodeGatesScanPanel(panel, extensionUri);
    }
    constructor(panel, extensionUri) {
        this.panel = panel;
        this.extensionUri = extensionUri;
        this.configManager = new configurationManager_1.ConfigurationManager();
        this.notificationManager = new notificationManager_1.NotificationManager();
        this.apiRunner = new apiRunner_1.ApiRunner(this.configManager, this.notificationManager);
        this.update();
        this.panel.onDidDispose(() => this.dispose(), null);
        this.panel.webview.onDidReceiveMessage(async (message) => {
            switch (message.command) {
                case 'testConnection':
                    await this.handleTestConnection();
                    break;
                case 'scan':
                    await this.handleScan(message.data);
                    break;
                case 'generateHtmlReport':
                    await this.handleGenerateHtmlReport(message.data);
                    break;
            }
        });
    }
    async handleTestConnection() {
        try {
            const isConnected = await this.apiRunner.testConnection();
            this.panel.webview.postMessage({
                command: 'connectionResult',
                data: { connected: isConnected }
            });
        }
        catch (error) {
            this.panel.webview.postMessage({
                command: 'connectionResult',
                data: { connected: false, error: error instanceof Error ? error.message : 'Unknown error' }
            });
        }
    }
    async handleScan(scanData) {
        try {
            this.panel.webview.postMessage({
                command: 'scanStarted',
                data: { message: 'Starting repository scan...' }
            });
            // Test connection first
            try {
                const isConnected = await this.apiRunner.testConnection();
                if (!isConnected) {
                    throw new Error('API server connection failed');
                }
            }
            catch (connectionError) {
                // Show user-friendly error dialog
                const startServer = await vscode.window.showErrorMessage('Failed to connect to API server. ' +
                    'To start the API server:\n1. Open terminal in VS Code (Terminal → New Terminal)\n2. Run: python3 start_server.py\n3. Wait for "Server started" message\n4. Try the scan again', 'Start Server', 'Show Instructions', 'Continue Anyway');
                if (startServer === 'Start Server') {
                    // Start API server
                    const terminal = vscode.window.createTerminal('MyGates API Server');
                    terminal.show();
                    terminal.sendText('python3 start_server.py');
                    vscode.window.showInformationMessage('Starting API server in terminal. Please wait for it to start, then try the scan again.');
                    this.panel.webview.postMessage({
                        command: 'scanError',
                        data: { error: 'API server is starting. Please wait and try again in a few seconds.' }
                    });
                    return;
                }
                else if (startServer === 'Show Instructions') {
                    vscode.window.showInformationMessage('To start the API server:\n1. Open terminal in VS Code (Terminal → New Terminal)\n2. Run: python3 start_server.py\n3. Wait for "Server started" message\n4. Try the scan again');
                    this.panel.webview.postMessage({
                        command: 'scanError',
                        data: { error: 'Please start the API server first. See the notification for instructions.' }
                    });
                    return;
                }
                else if (startServer !== 'Continue Anyway') {
                    this.panel.webview.postMessage({
                        command: 'scanError',
                        data: { error: 'API server connection required for scanning.' }
                    });
                    return;
                }
            }
            const options = {
                threshold: scanData.threshold || 70
            };
            this.panel.webview.postMessage({
                command: 'scanProgress',
                data: { message: 'Connecting to repository...' }
            });
            const result = await this.apiRunner.scanRepository(scanData.repositoryUrl, scanData.branch || 'main', scanData.githubToken, options);
            // Add repository URL to result for better display
            result.repository_url = scanData.repositoryUrl;
            this.panel.webview.postMessage({
                command: 'scanCompleted',
                data: result
            });
        }
        catch (error) {
            console.error('Scan error:', error);
            let errorMessage = error.message || 'Unknown error occurred';
            // Provide helpful error messages
            if (errorMessage.includes('Repository is private')) {
                errorMessage = 'This repository is private. Please provide a GitHub token with "repo" scope access.';
            }
            else if (errorMessage.includes('Invalid GitHub token')) {
                errorMessage = 'The GitHub token is invalid or expired. Please generate a new token with "repo" scope.';
            }
            else if (errorMessage.includes('Cannot access repository')) {
                errorMessage = 'Cannot access this repository. Check if the URL is correct and the token has proper permissions.';
            }
            else if (errorMessage.includes('ECONNREFUSED')) {
                errorMessage = 'Cannot connect to API server. Please start the server first.';
            }
            this.panel.webview.postMessage({
                command: 'scanError',
                data: { error: errorMessage }
            });
            // Show notification for critical errors
            if (errorMessage.includes('API server')) {
                vscode.window.showErrorMessage(`CodeGates: ${errorMessage}`);
            }
        }
    }
    async handleGenerateHtmlReport(data) {
        try {
            // Get a better default path - use workspace folder or home directory
            let defaultUri;
            if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
                // Use the workspace folder if available
                defaultUri = vscode.Uri.joinPath(vscode.workspace.workspaceFolders[0].uri, 'codegates-report.html');
            }
            else {
                // Fall back to home directory
                const os = require('os');
                const path = require('path');
                const homePath = path.join(os.homedir(), 'codegates-report.html');
                defaultUri = vscode.Uri.file(homePath);
            }
            // Show save dialog to let user choose where to save the HTML report
            const saveUri = await vscode.window.showSaveDialog({
                defaultUri: defaultUri,
                filters: {
                    'HTML Files': ['html'],
                    'All Files': ['*']
                }
            });
            if (!saveUri) {
                return; // User cancelled
            }
            // Generate HTML report with comments
            const htmlContent = await this.generateHtmlReportWithComments(data.result, data.comments);
            // Write to file
            await vscode.workspace.fs.writeFile(saveUri, Buffer.from(htmlContent, 'utf8'));
            // Show success message with option to open
            const openFile = await vscode.window.showInformationMessage(`HTML report generated successfully: ${saveUri.fsPath}`, 'Open Report', 'Open in Browser');
            if (openFile === 'Open Report') {
                vscode.window.showTextDocument(saveUri);
            }
            else if (openFile === 'Open in Browser') {
                vscode.env.openExternal(saveUri);
            }
        }
        catch (error) {
            console.error('Generate HTML report error:', error);
            vscode.window.showErrorMessage(`Failed to generate HTML report: ${error.message}`);
        }
    }
    async generateHtmlReportWithComments(result, comments) {
        // Generate HTML report with embedded comments using consistent logic
        const timestamp = new Date().toLocaleString();
        const projectName = this.extractProjectName(result.repository_url || 'Repository Scan Results');
        // Calculate stats with fixed logical consistency
        const totalGates = result.gates.length;
        let implementedGates = 0;
        let partialGates = 0;
        let notImplementedGates = 0;
        // Apply same logical consistency fixes as backend
        for (const gate of result.gates) {
            const found = gate.found || 0;
            const status = gate.status;
            // Apply logical consistency fixes
            if (found > 0 && gate.name === 'avoid_logging_secrets') {
                // Secrets violations should be counted as not implemented
                notImplementedGates += 1;
            }
            else if (found > 0 && status === 'PASS') {
                // Other gates with violations but PASS status should be partial
                partialGates += 1;
            }
            else if (status === 'PASS') {
                implementedGates += 1;
            }
            else if (status === 'WARNING') {
                partialGates += 1;
            }
            else if (status === 'FAIL' || status === 'FAILED') {
                notImplementedGates += 1;
            }
            else {
                // Default fallback
                notImplementedGates += 1;
            }
        }
        const commentsCount = Object.keys(comments || {}).length;
        // Generate gates table with comments
        const gatesTableHtml = this.generateGatesTableHtml(result.gates, comments);
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hard Gate Assessment - ${projectName}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #374151; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f3f4f6; }
        h1 { font-size: 2em; color: #1f2937; border-bottom: 3px solid #2563eb; padding-bottom: 15px; margin-bottom: 30px; }
        h2 { color: #1f2937; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-top: 40px; }
        h3 { color: #374151; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1); border: 1px solid #e5e7eb; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #2563eb; color: #fff; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
        tr:hover { background: #f9fafb; }
        .status-implemented { color: #059669; background: #ecfdf5; padding: 4px 8px; border-radius: 4px; font-weight: 500; }
        .status-partial { color: #d97706; background: #fffbeb; padding: 4px 8px; border-radius: 4px; font-weight: 500; }
        .status-not-implemented { color: #dc2626; background: #fef2f2; padding: 4px 8px; border-radius: 4px; font-weight: 500; }
        .summary-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }
        .stat-card { background: #fff; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #2563eb; }
        .stat-label { color: #6b7280; margin-top: 5px; }
        .compliance-bar { width: 100%; height: 20px; background: #e5e7eb; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .compliance-fill { height: 100%; background: linear-gradient(90deg, #dc2626 0%, #d97706 50%, #059669 100%); transition: width 0.3s ease; }
        .comment-cell { font-style: italic; color: #6b7280; max-width: 250px; word-wrap: break-word; background: #f9fafb; }
    </style>
</head>
<body>
    <div class="report-container">
        <h1>${projectName}</h1>
        <p style="color: #2563eb; margin-bottom: 30px; font-weight: 500;">Hard Gate Assessment Report${commentsCount > 0 ? ` (with ${commentsCount} user comments)` : ''}</p>
        
        <h2>Executive Summary</h2>
        
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-number">${totalGates}</div>
                <div class="stat-label">Total Gates Evaluated</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${implementedGates}</div>
                <div class="stat-label">Gates Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${partialGates}</div>
                <div class="stat-label">Partially Met</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${notImplementedGates}</div>
                <div class="stat-label">Not Met</div>
            </div>
        </div>
        
        <h3>Overall Compliance</h3>
        <div class="compliance-bar">
            <div class="compliance-fill" style="width: ${result.score || 0}%"></div>
        </div>
        <p><strong>${(result.score || 0).toFixed(1)}% Hard Gates Compliance</strong></p>
        
        <h2>Hard Gates Analysis</h2>
        ${gatesTableHtml}
        
        <footer style="margin-top: 50px; text-align: center; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 20px;">
            <p>Hard Gate Assessment Report generated on ${timestamp}</p>
            ${commentsCount > 0 ? `<p style="font-size: 0.9em; color: #9ca3af;">Report includes ${commentsCount} user comments for enhanced documentation</p>` : ''}
        </footer>
    </div>
</body>
</html>`;
    }
    generateGatesTableHtml(gates, comments) {
        const gateCategories = {
            'Auditability': ['structured_logs', 'avoid_logging_secrets', 'audit_trail', 'correlation_id', 'log_api_calls', 'log_background_jobs', 'ui_errors'],
            'Availability': ['retry_logic', 'timeouts', 'throttling', 'circuit_breakers'],
            'Error Handling': ['error_logs', 'http_codes', 'ui_error_tools'],
            'Testing': ['automated_tests']
        };
        const gateNameMap = {
            'structured_logs': 'Logs Searchable Available',
            'avoid_logging_secrets': 'Avoid Logging Confidential Data',
            'audit_trail': 'Create Audit Trail Logs',
            'correlation_id': 'Tracking ID For Log Messages',
            'log_api_calls': 'Log Rest API Calls',
            'log_background_jobs': 'Log Application Messages',
            'ui_errors': 'Client UI Errors Logged',
            'retry_logic': 'Retry Logic',
            'timeouts': 'Set Timeouts IO Operations',
            'throttling': 'Throttling Drop Request',
            'circuit_breakers': 'Circuit Breakers Outgoing Requests',
            'error_logs': 'Log System Errors',
            'http_codes': 'Use HTTP Standard Error Codes',
            'ui_error_tools': 'Include Client Error Tracking',
            'automated_tests': 'Automated Regression Testing'
        };
        let html = '';
        Object.entries(gateCategories).forEach(([categoryName, gateNames]) => {
            const categoryGates = gates.filter(gate => gateNames.includes(gate.name));
            if (categoryGates.length === 0)
                return;
            html += `
                <div class="gate-category">
                    <h3>${categoryName}</h3>
                    <table class="gates-table">
                        <thead>
                            <tr>
                                <th>Practice</th>
                                <th>Status</th>
                                <th>Evidence</th>
                                <th>Recommendation</th>
                                <th>Comments</th>
                            </tr>
                        </thead>
                        <tbody>`;
            categoryGates.forEach(gate => {
                const gateName = gateNameMap[gate.name] || this.formatGateName(gate.name);
                const statusInfo = this.getStatusInfo(gate);
                const evidence = this.formatEvidence(gate);
                const recommendation = this.getRecommendation(gate, gateName);
                const comment = comments[gate.name] || 'No comments';
                html += `
                            <tr>
                                <td><strong>${gateName}</strong></td>
                                <td><span class="status-${statusInfo.class}">${statusInfo.text}</span></td>
                                <td>${evidence}</td>
                                <td>${recommendation}</td>
                                <td class="comment-cell">${comment}</td>
                            </tr>`;
            });
            html += `
                        </tbody>
                    </table>
                </div>`;
        });
        return html;
    }
    getStatusInfo(gate) {
        // Apply logical consistency fixes for status display
        const found = gate.found || 0;
        const status = gate.status;
        // Fix logical inconsistency: if there are violations, show as warning/fail regardless of status
        if (found > 0 && gate.name === 'avoid_logging_secrets') {
            return { class: 'not-implemented', text: '✗ Violations Found' };
        }
        else if (found > 0 && status === 'PASS') {
            return { class: 'partial', text: '⚬ Has Issues' };
        }
        // Default status mapping
        switch (status) {
            case 'PASS':
                return { class: 'implemented', text: '✓ Implemented' };
            case 'WARNING':
                return { class: 'partial', text: '⚬ Partial' };
            case 'NOT_APPLICABLE':
                return { class: 'partial', text: 'N/A' };
            default:
                return { class: 'not-implemented', text: '✗ Missing' };
        }
    }
    formatEvidence(gate) {
        if (gate.status === 'NOT_APPLICABLE') {
            return 'Not applicable to this project type';
        }
        const found = gate.found || 0;
        const coverage = gate.coverage || 0;
        if (found > 0) {
            return `Found ${found} implementations with ${coverage.toFixed(1)}% coverage`;
        }
        else {
            return 'No relevant patterns found in codebase';
        }
    }
    getRecommendation(gate, gateName) {
        const found = gate.found || 0;
        const status = gate.status;
        // Fix logical inconsistency: if there are violations, recommend fixing them
        if (found > 0) {
            if (gate.name === 'avoid_logging_secrets') {
                return `Fix confidential data logging violations in ${gateName.toLowerCase()}`;
            }
            else if (status === 'PASS') {
                return `Address identified issues in ${gateName.toLowerCase()}`;
            }
        }
        // Default recommendation mapping
        switch (status) {
            case 'PASS':
                return 'Continue maintaining good practices';
            case 'WARNING':
                return `Expand implementation of ${gateName.toLowerCase()}`;
            case 'NOT_APPLICABLE':
                return 'Not applicable to this project type';
            default:
                return `Implement ${gateName.toLowerCase()}`;
        }
    }
    extractProjectName(repositoryUrl) {
        try {
            const urlParts = repositoryUrl.split('/');
            let projectName = urlParts[urlParts.length - 1] || 'Repository Scan Results';
            if (projectName.endsWith('.git')) {
                projectName = projectName.slice(0, -4);
            }
            return projectName;
        }
        catch {
            return 'Repository Scan Results';
        }
    }
    formatGateName(name) {
        return name.split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    update() {
        if (this.panel) {
            this.panel.webview.html = this.getHtmlForWebview(this.panel.webview);
        }
    }
    getHtmlForWebview(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, 'media', 'style.css'));
        return `<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="${styleUri}" rel="stylesheet">
                <title>CodeGates Repository Scan</title>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>CodeGates Repository Scan</h1>
                        <p>Validate your repository against production-ready quality gates</p>
                    </div>

                    <div class="scan-form">
                        <div class="form-group">
                            <label for="repositoryUrl">GitHub Repository URL</label>
                            <input type="text" id="repositoryUrl" placeholder="https://github.com/owner/repo or https://github.enterprise.com/owner/repo">
                            <small>Enter the full GitHub repository URL (supports github.com and GitHub Enterprise)</small>
                        </div>
                        <div class="form-group">
                            <label for="branch">Branch (defaults to main)</label>
                            <input type="text" id="branch" value="main" placeholder="main">
                            <small>The branch to scan, defaults to 'main' if not specified</small>
                        </div>
                        <div class="form-group">
                            <label for="githubToken">GitHub Token (Optional)</label>
                            <input type="password" id="githubToken" placeholder="ghp_xxxxxxxxxxxx">
                            <small>
                                A GitHub token with 'repo' scope is required for private repositories. 
                                <a href="https://github.com/settings/tokens" target="_blank">Generate one here</a>
                            </small>
                        </div>
                        <div class="form-group">
                            <label for="threshold">Quality Threshold</label>
                            <select id="threshold">
                                <option value="60">60% - Basic (Lenient)</option>
                                <option value="70" selected>70% - Standard (Recommended)</option>
                                <option value="80">80% - High (Strict)</option>
                                <option value="90">90% - Enterprise (Very Strict)</option>
                            </select>
                        </div>

                        <div class="form-actions">
                            <button id="scanButton" onclick="startScan()">Start Scan</button>
                            <button class="secondary" onclick="testConnection()">Test API Connection</button>
                        </div>
                    </div>

                    <div id="status" class="status hidden"></div>
                    <div id="results" class="results" style="display: none;"></div>
                </div>
                <script src="${scriptUri}"></script>
            </body>
            </html>`;
    }
    dispose() {
        CodeGatesScanPanel.currentPanel = undefined;
        this.panel.dispose();
    }
}
function activate(context) {
    let scanDisposable = vscode.commands.registerCommand('codegates.scan', () => {
        CodeGatesScanPanel.createOrShow(context.extensionUri);
    });
    let configureDisposable = vscode.commands.registerCommand('codegates.configure', () => {
        // Open VS Code settings for CodeGates
        vscode.commands.executeCommand('workbench.action.openSettings', 'codegates');
    });
    // Add debug command to test configuration
    let debugConfigDisposable = vscode.commands.registerCommand('codegates.debugConfig', () => {
        const configManager = new configurationManager_1.ConfigurationManager();
        const config = configManager.getAll();
        const message = `CodeGates Configuration:
API URL: ${config.apiUrl}
API Timeout: ${config.apiTimeout}
API Retries: ${config.apiRetries}

Settings inspection:
${JSON.stringify(config, null, 2)}`;
        vscode.window.showInformationMessage('Configuration details logged to console');
        console.log(message);
        // Also show in output channel
        const outputChannel = vscode.window.createOutputChannel('CodeGates Config');
        outputChannel.clear();
        outputChannel.appendLine(message);
        outputChannel.show();
    });
    context.subscriptions.push(scanDisposable, configureDisposable, debugConfigDisposable);
}
function deactivate() { }
//# sourceMappingURL=extension.js.map