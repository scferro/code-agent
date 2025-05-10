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
    
    @tool
    def run_python_script(file_path, args=""):
        """Run a Python script (requires permission)."""
        try:
            full_path = project_context.project_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                return f"Error: File '{file_path}' does not exist"
                
            if not full_path.is_file():
                return f"Error: '{file_path}' is not a file"
            
            # Check permission
            if not perm_manager.check_permission("execute", f"python {file_path} {args}"):
                perm_granted = perm_manager.request_permission(
                    "execute", 
                    f"Run Python script: {file_path} {args}",
                    "This will execute a Python script on your system."
                )
                
                if not perm_granted:
                    return "Permission denied: Cannot execute Python script"
            
            # Get Python executable (use the same Python that's running this code)
            python_exe = sys.executable
            
            # Prepare command
            cmd = [python_exe, str(full_path)]
            if args:
                cmd.extend(args.split())
            
            # Execute command
            result = subprocess.run(
                cmd,
                cwd=project_context.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Format output
            output = []
            output.append(f"Script: {file_path} {args}")
            output.append(f"Exit Code: {result.returncode}")
            
            if result.stdout:
                output.append("\nStandard Output:")
                output.append(result.stdout)
            
            if result.stderr:
                output.append("\nStandard Error:")
                output.append(result.stderr)
            
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return f"Script execution timed out after 30 seconds: {file_path}"
        except Exception as e:
            return f"Error running Python script: {str(e)}"
    
    @tool
    def execute_code_snippet(code, language="python"):
        """Execute a code snippet (requires permission)."""
        try:
            # Create a temporary file
            temp_dir = project_context.cache_dir / "snippets"
            temp_dir.mkdir(exist_ok=True)
            
            # Create filename based on language
            ext = {
                "python": ".py",
                "javascript": ".js",
                "node": ".js",
                "bash": ".sh",
                "shell": ".sh"
            }.get(language.lower(), ".txt")
            
            temp_file = temp_dir / f"snippet_{int(time.time())}{ext}"
            
            # Write code to temporary file
            with open(temp_file, "w") as f:
                f.write(code)
            
            # Check permission
            if not perm_manager.check_permission("execute", f"execute snippet ({language})"):
                perm_granted = perm_manager.request_permission(
                    "execute", 
                    f"Execute code snippet ({language})",
                    "This will execute a code snippet on your system."
                )
                
                if not perm_granted:
                    return "Permission denied: Cannot execute code snippet"
            
            # Execute based on language
            if language.lower() in ["python", "py"]:
                python_exe = sys.executable
                cmd = [python_exe, str(temp_file)]
            elif language.lower() in ["javascript", "js", "node"]:
                cmd = ["node", str(temp_file)]
            elif language.lower() in ["bash", "shell", "sh"]:
                cmd = ["bash", str(temp_file)]
            else:
                return f"Unsupported language: {language}"
            
            # Execute
            result = subprocess.run(
                cmd,
                cwd=project_context.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            # Format output
            output = []
            output.append(f"Language: {language}")
            output.append(f"Exit Code: {result.returncode}")
            
            if result.stdout:
                output.append("\nStandard Output:")
                output.append(result.stdout)
            
            if result.stderr:
                output.append("\nStandard Error:")
                output.append(result.stderr)
            
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return f"Code execution timed out after 30 seconds"
        except Exception as e:
            return f"Error executing code snippet: {str(e)}"
    
    return [execute_command, run_python_script, execute_code_snippet]