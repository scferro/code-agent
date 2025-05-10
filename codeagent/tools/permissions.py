"""Permission management for tool execution"""
import os
from pathlib import Path
import json
from typing import Dict, Set, Optional, Any
import time

class PermissionManager:
    """Manages permissions for tool execution"""
    
    def __init__(self):
        self.permission_cache = {
            "session": set(),      # Temporary for this session
            "project": dict(),     # Per project (stored in .codeagent/permissions.json)
            "global": dict()       # Global (stored in ~/.codeagent/permissions.json)
        }
        
        # Load global permissions
        self.global_config_path = Path.home() / ".codeagent"
        self.global_config_path.mkdir(exist_ok=True)
        self.global_permissions_path = self.global_config_path / "permissions.json"
        self._load_permissions()
    
    def _load_permissions(self):
        """Load permissions from disk"""
        # Load global permissions
        if self.global_permissions_path.exists():
            try:
                with open(self.global_permissions_path, "r") as f:
                    self.permission_cache["global"] = json.load(f)
            except Exception as e:
                print(f"Error loading global permissions: {e}")
                self.permission_cache["global"] = dict()
        
        # Project permissions are loaded on demand in check_permission
    
    def _save_permissions(self, scope="global"):
        """Save permissions to disk"""
        if scope == "global":
            with open(self.global_permissions_path, "w") as f:
                json.dump(self.permission_cache["global"], f)
        elif scope == "project" and hasattr(self, "project_permissions_path"):
            with open(self.project_permissions_path, "w") as f:
                json.dump(self.permission_cache["project"], f)
    
    def _load_project_permissions(self, project_dir: Path):
        """Load project-specific permissions"""
        # Set up project permissions path
        project_config_dir = project_dir / ".codeagent"
        project_config_dir.mkdir(exist_ok=True)
        self.project_permissions_path = project_config_dir / "permissions.json"
        
        # Load project permissions
        if self.project_permissions_path.exists():
            try:
                with open(self.project_permissions_path, "r") as f:
                    self.permission_cache["project"] = json.load(f)
            except Exception as e:
                print(f"Error loading project permissions: {e}")
                self.permission_cache["project"] = dict()
    
    def check_permission(self, permission_type: str, operation: str) -> bool:
        """Check if a permission has been granted"""
        # Check session permissions (exact match)
        permission_key = f"{permission_type}:{operation}"
        if permission_key in self.permission_cache["session"]:
            return True
        
        # Check project permissions (pattern matching)
        for pattern, timestamp in self.permission_cache["project"].items():
            if self._matches_pattern(permission_type, operation, pattern):
                # Check if permission has expired (7 days)
                if time.time() - timestamp < 7 * 24 * 60 * 60:
                    return True
        
        # Check global permissions (pattern matching)
        for pattern, timestamp in self.permission_cache["global"].items():
            if self._matches_pattern(permission_type, operation, pattern):
                # Check if permission has expired (30 days)
                if time.time() - timestamp < 30 * 24 * 60 * 60:
                    return True
        
        return False
    
    def _matches_pattern(self, permission_type: str, operation: str, pattern: str) -> bool:
        """Check if an operation matches a permission pattern"""
        try:
            pattern_type, pattern_op = pattern.split(":", 1)
            
            # Type must match exactly
            if permission_type != pattern_type:
                return False
            
            # Check operation
            if pattern_op == "*":
                return True
            elif pattern_op.endswith("*"):
                # Prefix match
                prefix = pattern_op[:-1]
                return operation.startswith(prefix)
            else:
                # Exact match
                return operation == pattern_op
        except Exception:
            return False
    
    def request_permission(self, permission_type: str, operation: str, 
                          description: str) -> bool:
        """Request permission from the user"""
        # Try to get the console from the parent CLI
        from rich.console import Console
        console = Console()
        
        # Ensure any spinners or statuses are stopped
        if hasattr(console, "status"):
            console.status.stop()  # This should stop any running spinner
        
        print(f"\n[!] Permission Required: {permission_type}")
        print(f"    {description}")
        print(f"    Operation: {operation}")
        print("\n    Options:")
        print("    1. Yes (this time only)")
        print("    2. Yes for this session")
        print("    3. Yes for this project (saved)")
        print("    4. Yes always (global)")
        print("    5. No (deny)")
        
        while True:
            choice = input("\n    Enter choice (1-5): ")
            
            if choice == "1":
                return True
            elif choice == "2":
                self._grant_session_permission(permission_type, operation)
                return True
            elif choice == "3":
                self._grant_project_permission(permission_type, operation)
                self._save_permissions("project")
                return True
            elif choice == "4":
                self._grant_global_permission(permission_type, operation)
                self._save_permissions("global")
                return True
            elif choice == "5":
                return False
            else:
                print("    Invalid choice. Please enter a number 1-5.")
    
    def _grant_session_permission(self, permission_type: str, operation: str):
        """Grant permission for the current session"""
        permission_key = f"{permission_type}:{operation}"
        self.permission_cache["session"].add(permission_key)
    
    def _grant_project_permission(self, permission_type: str, operation: str):
        """Grant permission for the current project"""
        # Create pattern based on operation
        if permission_type == "write":
            # For write, we want to match the specific file
            pattern = f"{permission_type}:{operation}"
        elif permission_type == "execute":
            # For execute, we want to match the command pattern
            # Remove arguments and exact paths
            parts = operation.split()
            if parts:
                pattern = f"{permission_type}:{parts[0]}*"
            else:
                pattern = f"{permission_type}:{operation}"
        else:
            pattern = f"{permission_type}:{operation}"
        
        # Save permission
        self.permission_cache["project"][pattern] = time.time()
    
    def _grant_global_permission(self, permission_type: str, operation: str):
        """Grant permission globally"""
        # Create pattern based on operation
        if permission_type == "write":
            # For write, we want to match the directory
            try:
                path = Path(operation)
                dir_path = path.parent
                pattern = f"{permission_type}:{dir_path}/*"
            except Exception:
                pattern = f"{permission_type}:{operation}"
        elif permission_type == "execute":
            # For execute, we want to match the command pattern
            # Remove arguments and exact paths
            parts = operation.split()
            if parts:
                pattern = f"{permission_type}:{parts[0]}*"
            else:
                pattern = f"{permission_type}:{operation}"
        else:
            pattern = f"{permission_type}:{operation}"
        
        # Save permission
        self.permission_cache["global"][pattern] = time.time()