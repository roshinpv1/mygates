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
exports.ConfigurationManager = void 0;
const vscode = __importStar(require("vscode"));
class ConfigurationManager {
    get(key, defaultValue) {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.get(key, defaultValue);
    }
    async update(key, value, target) {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        await config.update(key, value, target || vscode.ConfigurationTarget.Workspace);
    }
    has(key) {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.has(key);
    }
    inspect(key) {
        const config = vscode.workspace.getConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
        return config.inspect(key);
    }
    getAll() {
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
    onDidChange(listener) {
        return vscode.workspace.onDidChangeConfiguration(listener);
    }
    isCodeGatesConfigurationChange(e) {
        return e.affectsConfiguration(ConfigurationManager.CONFIGURATION_SECTION);
    }
}
exports.ConfigurationManager = ConfigurationManager;
ConfigurationManager.CONFIGURATION_SECTION = 'codegates';
//# sourceMappingURL=configurationManager.js.map