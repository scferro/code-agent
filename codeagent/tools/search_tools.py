"""Search and navigation tools for code exploration"""
from langchain.tools import tool
from codeagent.tools.permissions import request_permission
import subprocess
import os
import shlex
from pathlib import Path

def get_search_tools(project_context):
    """Get search and navigation tools"""
    
    @tool
    def grep_files(pattern, file_pattern="*", directory=".", include_line_numbers=True):
        """Search for text patterns in files using grep.
        
        Args:
            pattern: Text or regex pattern to search for
            file_pattern: File pattern to search in (e.g., "*.py", "*.js", "*")
            directory: Directory to search in (default: current directory)
            include_line_numbers: Whether to show line numbers (default: True)
        """
        try:
            # Request permission before executing search
            if not request_permission("search", f"Search for pattern '{pattern}' in {file_pattern} files", f"This will search files in {directory}"):
                return "Permission denied: Cannot execute search"
            
            # Build command - prefer ripgrep (rg) if available, fallback to grep
            base_dir = project_context.project_dir / directory
            if not base_dir.exists():
                return f"Error: Directory '{directory}' does not exist"
            
            # Check if ripgrep is available
            try:
                subprocess.run(["rg", "--version"], capture_output=True, check=True)
                use_rg = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                use_rg = False
            
            if use_rg:
                # Use ripgrep - faster and better
                cmd = ["rg"]
                if include_line_numbers:
                    cmd.append("-n")
                cmd.extend(["--type-add", f"target:{file_pattern}"])
                cmd.extend(["-t", "target"])
                cmd.extend(["--color", "never"])
                cmd.append(pattern)
                cmd.append(str(base_dir))
            else:
                # Fallback to grep
                cmd = ["grep", "-r"]
                if include_line_numbers:
                    cmd.append("-n")
                cmd.extend(["--include", file_pattern])
                cmd.append(pattern)
                cmd.append(str(base_dir))
            
            # Execute search with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=project_context.project_dir
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output:
                    return f"No matches found for pattern '{pattern}' in {file_pattern} files"
                
                # Limit output size
                if len(output) > 50000:  # 50KB limit
                    lines = output.split('\n')
                    output = '\n'.join(lines[:500]) + f"\n... (truncated, showing first 500 matches)"
                
                return f"Search results for pattern '{pattern}' in {file_pattern} files:\n\n{output}"
            elif result.returncode == 1:
                return f"No matches found for pattern '{pattern}' in {file_pattern} files"
            else:
                error = result.stderr.strip()
                return f"Error executing search: {error}"
                
        except subprocess.TimeoutExpired:
            return "Error: Search timed out after 30 seconds"
        except Exception as e:
            return f"Error executing search: {str(e)}"
    
    @tool
    def find_files(name_pattern, directory=".", max_depth=5):
        """Find files by name pattern.
        
        Args:
            name_pattern: File name pattern (e.g., "*.py", "*test*", "config.*")
            directory: Directory to search in (default: current directory)
            max_depth: Maximum depth to search (default: 5)
        """
        try:
            # Request permission before executing find
            if not request_permission("search", f"Find files matching '{name_pattern}'", f"This will search for files in {directory}"):
                return "Permission denied: Cannot execute file search"
            
            base_dir = project_context.project_dir / directory
            if not base_dir.exists():
                return f"Error: Directory '{directory}' does not exist"
            
            # Build find command
            cmd = ["find", str(base_dir)]
            cmd.extend(["-maxdepth", str(max_depth)])
            cmd.extend(["-name", name_pattern])
            cmd.extend(["-type", "f"])  # Only files, not directories
            
            # Execute find with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=project_context.project_dir
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output:
                    return f"No files found matching pattern '{name_pattern}'"
                
                # Convert absolute paths to relative paths
                lines = output.split('\n')
                relative_paths = []
                for line in lines:
                    try:
                        rel_path = Path(line).relative_to(project_context.project_dir)
                        relative_paths.append(str(rel_path))
                    except ValueError:
                        relative_paths.append(line)
                
                # Limit results
                if len(relative_paths) > 200:
                    relative_paths = relative_paths[:200]
                    relative_paths.append("... (truncated, showing first 200 results)")
                
                file_count = len([p for p in relative_paths if not p.startswith("...")])
                return f"Found {file_count} files matching pattern '{name_pattern}':\n\n" + '\n'.join(relative_paths)
            else:
                error = result.stderr.strip()
                return f"Error executing file search: {error}"
                
        except subprocess.TimeoutExpired:
            return "Error: File search timed out after 30 seconds"
        except Exception as e:
            return f"Error executing file search: {str(e)}"
    
    return [grep_files, find_files]