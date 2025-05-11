"""Tools for executing commands"""
from langchain.tools import BaseTool, StructuredTool, tool
import subprocess
from pathlib import Path
import os
import sys
from typing import List, Dict, Any, Optional

from codeagent.tools.permissions import PermissionManager

def get_execution_tools(project_context):
    """Get execution-related tools"""
    perm_manager = PermissionManager()
    
    @tool
    def execute_command(command):
        """Execute a shell command (requires permission)."""
        try:
            # Check permission
            if not perm_manager.check_permission("execute", command):
                perm_granted = perm_manager.request_permission(
                    "execute", 
                    f"Execute command: {command}", 
                    "This will run a shell command on your system."
                )
                
                if not perm_granted:
                    return "Permission denied: Cannot execute command"
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=project_context.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Format output
            output = []
            output.append(f"Command: {command}")
            output.append(f"Exit Code: {result.returncode}")
            
            if result.stdout:
                output.append("\nStandard Output:")
                output.append(result.stdout)
            
            if result.stderr:
                output.append("\nStandard Error:")
                output.append(result.stderr)
            
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return f"Command timed out after 30 seconds: {command}"
        except Exception as e:
            return f"Error executing command: {str(e)}"