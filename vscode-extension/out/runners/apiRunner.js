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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApiRunner = void 0;
const vscode = __importStar(require("vscode"));
const axios_1 = __importDefault(require("axios"));
class ApiRunner {
    constructor(configManager, notificationManager) {
        this.pollingInterval = null;
        this.configManager = configManager;
        this.notificationManager = notificationManager;
        this.client = this.createHttpClient();
        // Listen for configuration changes
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('codegates.api')) {
                this.client = this.createHttpClient();
            }
        });
    }
    createHttpClient() {
        const config = this.getApiConfig();
        const client = axios_1.default.create({
            baseURL: config.baseUrl,
            timeout: config.timeout * 1000,
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': 'CodeGates-VSCode/1.0.0'
            }
        });
        if (config.apiKey) {
            client.defaults.headers.common['Authorization'] = `Bearer ${config.apiKey}`;
        }
        client.interceptors.request.use((config) => {
            console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
            return config;
        }, (error) => {
            console.error('API Request Error:', error);
            return Promise.reject(error);
        });
        client.interceptors.response.use((response) => {
            console.log(`API Response: ${response.status} ${response.config.url}`);
            return response;
        }, (error) => {
            console.error('API Response Error:', error.response?.status, error.response?.data);
            return Promise.reject(error);
        });
        return client;
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
            const response = await this.client.get('/health');
            console.log('Health check response:', response.status, response.data);
            return response.status === 200;
        }
        catch (error) {
            console.error('API connection test failed:', error);
            // Provide specific error messages
            if (error.code === 'ECONNREFUSED') {
                throw new Error('Cannot connect to API server. Please ensure the API server is running on http://localhost:8000');
            }
            else if (error.response?.status === 404) {
                throw new Error('API endpoint not found. Please check the API server configuration.');
            }
            else if (error.response?.status >= 500) {
                throw new Error('API server error. Please check the server logs.');
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
            // Start the scan
            const response = await this.client.post('/scan', requestData);
            const initialResult = this.transformApiResult(response.data);
            // If scan is running, poll for completion
            if (initialResult.status === 'running') {
                return await this.pollForCompletion(initialResult.scan_id);
            }
            return initialResult;
        }
        catch (error) {
            console.error('Scan repository error:', error);
            // Handle specific API errors
            if (error.response?.data?.detail) {
                const detail = error.response.data.detail;
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
            // Handle connection errors
            if (error.code === 'ECONNREFUSED') {
                throw new Error('Cannot connect to API server. Please start the API server first.');
            }
            // Handle other errors
            if (error.response?.status === 404) {
                throw new Error('API endpoint not found. Please check the API server configuration.');
            }
            if (error.response?.status >= 500) {
                throw new Error('API server internal error. Please check the server logs.');
            }
            throw new Error(`Repository scan failed: ${this.getErrorMessage(error)}`);
        }
    }
    async pollForCompletion(scanId) {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 60; // 5 minutes at 5-second intervals
            const poll = async () => {
                try {
                    attempts++;
                    if (attempts > maxAttempts) {
                        reject(new Error('Scan timeout - operation took too long to complete'));
                        return;
                    }
                    const result = await this.getScanStatus(scanId);
                    if (result.status === 'completed') {
                        resolve(result);
                    }
                    else if (result.status === 'failed') {
                        reject(new Error(result.message || 'Scan failed'));
                    }
                    else {
                        // Still running, continue polling
                        setTimeout(poll, 5000); // Poll every 5 seconds
                    }
                }
                catch (error) {
                    reject(error);
                }
            };
            poll();
        });
    }
    async getScanStatus(scanId) {
        try {
            const response = await this.client.get(`/scan/${scanId}/status`);
            return this.transformApiResult(response.data);
        }
        catch (error) {
            throw new Error(`Failed to get scan status: ${this.getErrorMessage(error)}`);
        }
    }
    transformApiResult(apiResult) {
        return {
            scan_id: apiResult.scan_id,
            status: apiResult.status,
            score: apiResult.score,
            gates: apiResult.gates.map((gate) => ({
                name: gate.name,
                status: gate.status,
                score: gate.score,
                details: gate.details || []
            })),
            recommendations: apiResult.recommendations || [],
            report_url: apiResult.report_url,
            progress: apiResult.progress,
            message: apiResult.message
        };
    }
    getErrorMessage(error) {
        if (error.response?.data?.message) {
            return error.response.data.message;
        }
        if (error.response?.data?.error) {
            return error.response.data.error;
        }
        if (error.message) {
            return error.message;
        }
        return 'Unknown error occurred';
    }
    dispose() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}
exports.ApiRunner = ApiRunner;
//# sourceMappingURL=apiRunner.js.map