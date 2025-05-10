"""Utilities for interacting with Ollama"""
import requests
import json
import subprocess
import sys
import time
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

class OllamaClient:
    """Client for interacting with Ollama"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._ensure_ollama_running()
    
    def _ensure_ollama_running(self):
        """Ensure Ollama is running, start if not"""
        try:
            response = requests.get(f"{self.base_url}")
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            # Ollama is not running, try to start it
            print("Ollama is not running. Attempting to start...")
            
            try:
                # Check if Ollama is installed
                if sys.platform == "darwin" or sys.platform.startswith("linux"):
                    # Check if ollama command exists
                    result = subprocess.run(
                        ["which", "ollama"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        print("Ollama is not installed. Please install it from https://ollama.ai")
                        return False
                    
                    # Start ollama
                    subprocess.Popen(
                        ["ollama", "serve"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    
                    # Wait for ollama to start
                    for _ in range(10):
                        time.sleep(1)
                        try:
                            response = requests.get(f"{self.base_url}")
                            if response.status_code == 200:
                                print("Ollama started successfully.")
                                return True
                        except requests.exceptions.ConnectionError:
                            pass
                    
                    print("Failed to start Ollama. Please start it manually with 'ollama serve'")
                    return False
                else:
                    print("Automatic Ollama startup not supported on this platform.")
                    print("Please start Ollama manually.")
                    return False
            except Exception as e:
                print(f"Error starting Ollama: {e}")
                return False
        
        return True
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List available models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                return response.json().get("models", [])
            return []
        except Exception as e:
            print(f"Error listing models: {e}")
            return []
    
    def check_model_available(self, model_name: str) -> bool:
        """Check if a model is available"""
        models = self.list_models()
        return any(model["name"] == model_name for model in models)
    
    def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama library"""
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            )
            
            # This is a streaming response
            return response.status_code == 200
        except Exception as e:
            print(f"Error pulling model: {e}")
            return False
    
    def generate(self, prompt: str, model: str = "codellama:7b-instruct", 
                system: Optional[str] = None, temperature: float = 0.7,
                max_tokens: int = 4096) -> str:
        """Generate text from a prompt"""
        try:
            # Ensure model is available
            if not self.check_model_available(model):
                print(f"Model {model} not available. Attempting to pull...")
                if not self.pull_model(model):
                    raise Exception(f"Failed to pull model {model}")
            
            # Generate
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            if system:
                payload["system"] = system
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                raise Exception(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Error generating text: {e}")
            return f"Error: {str(e)}"
    
    def get_embedding(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Get embedding for text"""
        try:
            # Ensure model is available
            if not self.check_model_available(model):
                print(f"Model {model} not available. Attempting to pull...")
                if not self.pull_model(model):
                    raise Exception(f"Failed to pull model {model}")
            
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text}
            )
            
            if response.status_code == 200:
                return response.json().get("embedding", [])
            else:
                raise Exception(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []