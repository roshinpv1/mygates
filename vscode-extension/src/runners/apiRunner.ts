/**
 * CodeGates API Runner
 * 
 * Communicates with CodeGates API server for remote scanning and analysis.
 * Provides the same interface as CLI runner but uses HTTP API calls.
 */

import * as vscode from 'vscode';
import axios, { AxiosInstance } from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { ConfigurationManager } from '../utils/configurationManager';
import { NotificationManager } from '../utils/notificationManager';
import { ApiConfig, ScanOptions, ScanRequest, ScanResult, GateResult, ICodeGatesRunner } from '../types/api';

export class ApiRunner implements ICodeGatesRunner {
    private client: AxiosInstance;
    private configManager: ConfigurationManager;
    private notificationManager: NotificationManager;
    private pollingInterval: NodeJS.Timeout | null = null;

    constructor(
        configManager: ConfigurationManager,
        notificationManager: NotificationManager
    ) {
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

    private createHttpClient(): AxiosInstance {
        const config = this.getApiConfig();
        
        const client = axios.create({
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

        client.interceptors.request.use(
            (config) => {
                console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
                return config;
            },
            (error) => {
                console.error('API Request Error:', error);
                return Promise.reject(error);
            }
        );

        client.interceptors.response.use(
            (response) => {
                console.log(`API Response: ${response.status} ${response.config.url}`);
                return response;
            },
            (error) => {
                console.error('API Response Error:', error.response?.status, error.response?.data);
                return Promise.reject(error);
            }
        );

        return client;
    }

    private getApiConfig(): ApiConfig {
        return {
            baseUrl: this.configManager.get<string>('api.baseUrl', 'http://localhost:8000/api/v1'),
            apiKey: this.configManager.get<string>('api.apiKey', ''),
            timeout: this.configManager.get<number>('api.timeout', 300),
            retries: this.configManager.get<number>('api.retries', 3)
        };
    }

    async testConnection(): Promise<boolean> {
        try {
            console.log('Testing API connection to:', this.getApiConfig().baseUrl);
            const response = await this.client.get('/health');
            console.log('Health check response:', response.status, response.data);
            return response.status === 200;
        } catch (error: any) {
            console.error('API connection test failed:', error);
            
            // Provide specific error messages
            if (error.code === 'ECONNREFUSED') {
                throw new Error('Cannot connect to API server. Please ensure the API server is running on http://localhost:8000');
            } else if (error.response?.status === 404) {
                throw new Error('API endpoint not found. Please check the API server configuration.');
            } else if (error.response?.status >= 500) {
                throw new Error('API server error. Please check the server logs.');
            } else {
                throw new Error(`API connection failed: ${error.message || 'Unknown error'}`);
            }
        }
    }

    async scanRepository(repoUrl: string, branch: string = 'main', token?: string, options: ScanOptions = {}): Promise<ScanResult> {
        try {
            // Test connection first
            try {
                await this.testConnection();
            } catch (connectionError: any) {
                throw new Error(`API Server Connection Failed: ${connectionError.message}`);
            }

            const requestData: ScanRequest = {
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

        } catch (error: any) {
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

    private async pollForCompletion(scanId: string): Promise<ScanResult> {
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
                    } else if (result.status === 'failed') {
                        reject(new Error(result.message || 'Scan failed'));
                    } else {
                        // Still running, continue polling
                        setTimeout(poll, 5000); // Poll every 5 seconds
                    }
                } catch (error) {
                    reject(error);
                }
            };

            poll();
        });
    }

    async getScanStatus(scanId: string): Promise<ScanResult> {
        try {
            const response = await this.client.get(`/scan/${scanId}/status`);
            return this.transformApiResult(response.data);
        } catch (error) {
            throw new Error(`Failed to get scan status: ${this.getErrorMessage(error)}`);
        }
    }

    private transformApiResult(apiResult: any): ScanResult {
        return {
            scan_id: apiResult.scan_id,
            status: apiResult.status,
            score: apiResult.score,
            gates: apiResult.gates.map((gate: any) => ({
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

    private getErrorMessage(error: any): string {
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

    dispose(): void {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
} 