import * as vscode from 'vscode';

export class ConfigurationManager {
    private static readonly CONFIGURATION_SECTION = 'codegates';

    get<T>(key: string, defaultValue?: T): T {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.get<T>(key, defaultValue as T);
    }

    async update(key: string, value: any, target?: vscode.ConfigurationTarget): Promise<void> {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        await config.update(key, value, target || vscode.ConfigurationTarget.Workspace);
    }

    has(key: string): boolean {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.has(key);
    }

    inspect(key: string) {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.inspect(key);
    }

    getAll(): { [key: string]: any } {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return {
            enabled: config.get('enabled'),
            autoScan: config.get('autoScan'),
            scanOnOpen: config.get('scanOnOpen'),
            threshold: config.get('threshold'),
            languages: config.get('languages'),
            excludePatterns: config.get('excludePatterns'),
            llm: {
                enabled: config.get('llm.enabled'),
                provider: config.get('llm.provider'),
                model: config.get('llm.model'),
                temperature: config.get('llm.temperature')
            },
            reports: {
                format: config.get('reports.format'),
                autoOpen: config.get('reports.autoOpen')
            },
            notifications: {
                level: config.get('notifications.level')
            },
            pythonPath: config.get('pythonPath'),
            codegatePath: config.get('codegatePath')
        };
    }

    onDidChange(listener: (e: vscode.ConfigurationChangeEvent) => void): vscode.Disposable {
        return vscode.workspace.onDidChangeConfiguration(listener);
    }

    isCodeGatesConfigurationChange(e: vscode.ConfigurationChangeEvent): boolean {
        return e.affectsConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
    }
} 