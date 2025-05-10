"""Configuration management for CodeAgent"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Default configuration
DEFAULT_CONFIG = {
    "models": {
        "default": "codellama:7b-instruct",
        "alternatives": [
            "codellama:13b-instruct",
            "codellama:34b-instruct",
            "mistral:7b-instruct",
            "llama3:8b-instruct"
        ]
    },
    "tools": {
        "enabled": [
            "file_tools",
            "code_tools",
            "execution_tools"
        ]
    },
    "embeddings": {
        "model": "nomic-embed-text",
        "chunk_size": 1000,
        "chunk_overlap": 200
    },
    "interface": {
        "show_thinking": False,
        "color_theme": "dark"
    }
}

# Global config object
_config = None

def load_config():
    """Load configuration from disk"""
    global _config
    
    # Look for config in multiple locations
    config_paths = [
        Path.cwd() / ".codeagent" / "config.json",  # Project config
        Path.home() / ".codeagent" / "config.json"  # Global config
    ]
    
    # Start with default config
    _config = DEFAULT_CONFIG.copy()
    
    # Load and merge configs in order (later configs override earlier ones)
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    user_config = json.load(f)
                
                # Merge with current config
                _deep_merge(_config, user_config)
            except Exception as e:
                print(f"Error loading config from {config_path}: {e}")
    
    return _config

def get_config(key: Optional[str] = None):
    """Get configuration value"""
    global _config
    
    # Load config if not already loaded
    if _config is None:
        load_config()
    
    # Return specific key or entire config
    if key is None:
        return _config
    
    # Support dot notation for nested keys
    if "." in key:
        parts = key.split(".")
        value = _config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value
    
    return _config.get(key)

def save_config(config: Dict[str, Any], scope: str = "project"):
    """Save configuration to disk"""
    if scope == "project":
        config_dir = Path.cwd() / ".codeagent"
    else:  # global
        config_dir = Path.home() / ".codeagent"
    
    # Create directory if it doesn't exist
    config_dir.mkdir(exist_ok=True, parents=True)
    
    # Write config
    config_path = config_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]):
    """Deep merge two dictionaries"""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            # Recursively merge dictionaries
            _deep_merge(target[key], value)
        else:
            # Override or add value
            target[key] = value