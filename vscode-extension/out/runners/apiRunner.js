"use strict";
/**
 * CodeGates API Runner
 *
 * Communicates with CodeGates API server for remote scanning and analysis.
 * Provides the same interface as CLI runner but uses HTTP API calls.
 */
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
exports.ApiRunner = void 0;
const vscode = __importStar(require("vscode"));
const https = __importStar(require("https"));
const http = __importStar(require("http"));
class ApiRunner {
    constructor(configManager, notificationManager) {
        this.pollingInterval = null;
        this.configManager = configManager;
        this.notificationManager = notificationManager;
        // Listen for configuration changes
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('codegates.api')) {
                // Configuration changed - no client to recreate since we're using built-in HTTP
            }
        });
    }
    async makeHttpRequest(method, endpoint, data, customTimeout) {
        const config = this.getApiConfig();
        const fullUrl = `${config.baseUrl}${endpoint}`;
        const urlParts = new URL(fullUrl);
        // Use shorter timeout for API calls (30 seconds) unless custom timeout specified
        const requestTimeout = customTimeout || 30000;
        const options = {
            hostname: urlParts.hostname,
            port: urlParts.port || (urlParts.protocol === 'https:' ? 443 : 80),
            path: urlParts.pathname + urlParts.search,
            method: method.toUpperCase(),
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': 'CodeGates-VSCode/2.0.3'
            },
            timeout: requestTimeout
        };
        if (config.apiKey) {
            options.headers['Authorization'] = `Bearer ${config.apiKey}`;
        }
        const httpModule = urlParts.protocol === 'https:' ? https : http;
        return new Promise((resolve, reject) => {
            const req = httpModule.request(options, (res) => {
                let responseData = '';
                res.on('data', (chunk) => {
                    responseData += chunk;
                });
                res.on('end', () => {
                    try {
                        const parsedData = responseData ? JSON.parse(responseData) : {};
                        resolve({
                            statusCode: res.statusCode || 0,
                            data: parsedData
                        });
                    }
                    catch (parseError) {
                        reject(new Error(`Failed to parse response: ${parseError}`));
                    }
                });
            });
            req.on('timeout', () => {
                req.destroy();
                reject(new Error(`Request timeout after ${requestTimeout / 1000} seconds`));
            });
            req.on('error', (error) => {
                reject(error);
            });
            if (data) {
                const jsonData = JSON.stringify(data);
                options.headers['Content-Length'] = Buffer.byteLength(jsonData);
                req.write(jsonData);
            }
            req.end();
        });
    }
    getApiConfig() {
        return {
            baseUrl: this.configManager.get('api.baseUrl', 'http://localhost:8000/api/v1'),
            apiKey: this.configManager.get('api.apiKey', ''),
            timeout: this.configManager.get('api.timeout', 300),
            retries: this.configManager.get('api.retries', 3)
        };
    }
    async testConnection() {
        try {
            console.log('Testing API connection to:', this.getApiConfig().baseUrl);
            const response = await this.makeHttpRequest('GET', '/health');
            console.log('Health check response:', response.statusCode, response.data);
            return response.statusCode === 200;
        }
        catch (error) {
            console.error('API connection test failed:', error);
            // Provide specific error messages
            if (error.code === 'ECONNREFUSED') {
                throw new Error('Cannot connect to API server. Please ensure the API server is running on http://localhost:8000');
            }
            else if (error.message?.includes('timeout')) {
                throw new Error('API server connection timeout. Please check if the server is responding.');
            }
            else {
                throw new Error(`API connection failed: ${error.message || 'Unknown error'}`);
            }
        }
    }
    async scanRepository(repoUrl, branch = 'main', token, options = {}) {
        try {
            // Test connection first
            try {
                await this.testConnection();
            }
            catch (connectionError) {
                throw new Error(`API Server Connection Failed: ${connectionError.message}`);
            }
            const requestData = {
                repository_url: repoUrl,
                branch,
                github_token: token,
                scan_options: options
            };
            console.log('Sending scan request:', {
                repository_url: repoUrl,
                branch,
                has_token: !!token,
                options
            });
            // Start the scan with longer timeout for the initial request
            const response = await this.makeHttpRequest('POST', '/scan', requestData, 60000); // 60 second timeout for scan start
            if (response.statusCode >= 400) {
                const errorData = response.data;
                if (errorData?.detail) {
                    const detail = errorData.detail;
                    if (detail.includes('Repository is private')) {
                        throw new Error('Repository is private. Please provide a GitHub token with repo scope.');
                    }
                    if (detail.includes('Invalid GitHub token')) {
                        throw new Error('Invalid GitHub token. Please check if the token has the required repo scope.');
                    }
                    if (detail.includes('Cannot access repository')) {
                        throw new Error('Cannot access repository. Please check if the token has access to this repository.');
                    }
                    throw new Error(detail);
                }
                throw new Error(`API request failed with status ${response.statusCode}`);
            }
            const initialResult = this.transformApiResult(response.data);
            // If scan is running, poll for completion (up to 15 minutes)
            if (initialResult.status === 'running') {
                console.log('Scan started, polling for completion (timeout: 15 minutes)...');
                return await this.pollForCompletion(initialResult.scan_id);
            }
            return initialResult;
        }
        catch (error) {
            console.error('Scan repository error:', error);
            // Handle connection errors
            if (error.code === 'ECONNREFUSED') {
                throw new Error('Cannot connect to API server. Please start the API server first.');
            }
            // Handle timeout errors with helpful message
            if (error.message?.includes('timeout')) {
                throw new Error('Repository scan timed out. Large repositories may take longer to analyze. Please try again or contact support if the issue persists.');
            }
            throw new Error(`Repository scan failed: ${this.getErrorMessage(error)}`);
        }
    }
    async pollForCompletion(scanId) {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 180; // 15 minutes at 5-second intervals
            const pollInterval = 5000; // 5 seconds
            const poll = async () => {
                try {
                    attempts++;
                    if (attempts > maxAttempts) {
                        reject(new Error('Scan timeout - repository scan took longer than 15 minutes to complete'));
                        return;
                    }
                    console.log(`Polling for scan completion: attempt ${attempts}/${maxAttempts}`);
                    const result = await this.getScanStatus(scanId);
                    if (result.status === 'completed') {
                        console.log('Scan completed successfully');
                        resolve(result);
                    }
                    else if (result.status === 'failed') {
                        reject(new Error(result.message || 'Scan failed'));
                    }
                    else {
                        // Still running, continue polling
                        console.log(`Scan still running... (${Math.round(attempts * pollInterval / 1000)}s elapsed)`);
                        setTimeout(poll, pollInterval);
                    }
                }
                catch (error) {
                    console.error('Error during polling:', error);
                    // If it's a network error, retry a few times before giving up
                    if (attempts < 5 && (error.code === 'ECONNREFUSED' || error.message?.includes('timeout'))) {
                        console.log('Network error during polling, retrying...');
                        setTimeout(poll, pollInterval);
                    }
                    else {
                        reject(error);
                    }
                }
            };
            // Start polling
            poll();
        });
    }
    async getScanStatus(scanId) {
        try {
            const response = await this.makeHttpRequest('GET', `/scan/${scanId}/status`);
            return this.transformApiResult(response.data);
        }
        catch (error) {
            throw new Error(`Failed to get scan status: ${this.getErrorMessage(error)}`);
        }
    }
    transformApiResult(apiResult) {
        return {
            scan_id: apiResult.scan_id || '',
            status: apiResult.status || 'unknown',
            message: apiResult.message || '',
            repository_url: apiResult.repository_url || '',
            score: apiResult.score || 0,
            gates: apiResult.gates || [],
            recommendations: apiResult.recommendations || [],
            report_url: apiResult.report_url || '',
            progress: apiResult.progress || 0,
            languages_detected: apiResult.languages_detected || []
        };
    }
    getErrorMessage(error) {
        if (error.response?.data?.message) {
            return error.response.data.message;
        }
        if (error.response?.data?.detail) {
            return error.response.data.detail;
        }
        if (error.message) {
            return error.message;
        }
        return 'Unknown error occurred';
    }
    dispose() {
        if (this.pollingInterval) {
            clearTimeout(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}
exports.ApiRunner = ApiRunner;
//# sourceMappingURL=apiRunner.js.map