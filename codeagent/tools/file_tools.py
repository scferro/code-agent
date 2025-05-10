"""File operation tools"""
from langchain.tools import BaseTool, StructuredTool, Tool, tool
from pathlib import Path
from typing import List, Dict, Any, Optional

from codeagent.tools.permissions import PermissionManager

def get_file_tools(project_context):
    """Get file operation tools"""
    perm_manager = PermissionManager()
    
    @tool
    def list_files(directory=".", recursive=True, max_depth=3):
        """List files in a directory. Use this to explore the project structure.

        Args:
            directory: The directory to list
            recursive: Whether to include files in subdirectories (default True)
            max_depth: Maximum depth to recursively list (default 3)
        """
        dir_path = project_context.project_dir / directory

        try:
            # Check if directory exists
            if not dir_path.exists():
                return f"Error: Directory '{directory}' does not exist"

            if not dir_path.is_dir():
                return f"Error: '{directory}' is not a directory"

            # Format output
            result = [f"Directory: {directory}"]

            # Group by type
            directories = []
            files = []

            # Function to recursively collect files with path depth tracking
            def collect_items(path, current_depth=0):
                if current_depth > max_depth:
                    return

                try:
                    # Get directory contents
                    items = list(path.iterdir())

                    # Sort directories first, then files
                    items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

                    for item in items:
                        # Calculate relative path from project root
                        rel_path = item.relative_to(project_context.project_dir)

                        if item.is_dir():
                            # Skip hidden directories
                            if item.name.startswith("."):
                                continue

                            # Add directory to list
                            indent = "  " * current_depth
                            directories.append(f"{indent}📁 {rel_path}/")

                            # Recursively process subdirectory if recursive flag is set
                            if recursive:
                                collect_items(item, current_depth + 1)
                        else:
                            # Skip hidden files
                            if item.name.startswith("."):
                                continue

                            # Add file size
                            size_kb = item.stat().st_size / 1024
                            if size_kb < 1:
                                size_str = f"{item.stat().st_size} bytes"
                            else:
                                size_str = f"{size_kb:.1f} KB"

                            # Add indent based on depth
                            indent = "  " * current_depth
                            files.append(f"{indent}📄 {rel_path} ({size_str})")
                except Exception as e:
                    files.append(f"Error accessing {path}: {str(e)}")

            # Start collection from the root directory
            collect_items(dir_path)

            # Add counts and items to result
            result.append(f"\nDirectories ({len(directories)}):")
            result.extend(directories)

            result.append(f"\nFiles ({len(files)}):")
            result.extend(files)

            # Track that this directory has been explored
            project_context.track_dir_exploration(directory)

            return "\n".join(result)
        except Exception as e:
            return f"Error listing directory: {e}"

    @tool
    def read_file(file_path):
        """Read the contents of a file. Use this to view code."""
        try:
            full_path = project_context.project_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                return f"Error: File '{file_path}' does not exist"
                
            if not full_path.is_file():
                return f"Error: '{file_path}' is not a file"
                
            # Read file
            content = full_path.read_text(errors='ignore')
            
            # Get file description if available
            description = project_context.get_file_description(file_path)
            description_str = f"\nDescription: {description}" if description else ""
            
            # Get file info
            file_info = f"File: {file_path}{description_str}"
            size_kb = full_path.stat().st_size / 1024
            if size_kb < 1:
                size_str = f"{full_path.stat().st_size} bytes"
            else:
                size_str = f"{size_kb:.1f} KB"
                
            file_info += f" ({size_str})"
            
            # Track that this file has been explored
            project_context.track_file_exploration(file_path)
            
            # Return formatted content
            separator = "=" * len(file_info)
            return f"{file_info}\n{separator}\n\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"

    @tool
    def search_code(query):
        """Search the codebase for relevant code using semantic search."""
        try:
            # Use semantic search
            results = project_context.search_code(query)
            
            if not results:
                return f"No results found for query: {query}"
                
            # Format results
            output = [f"Search results for: '{query}'"]
            
            for i, result in enumerate(results, 1):
                file_path = result["file_path"]
                score = result["score"] if "score" in result else "Unknown"
                content = result["content"]
                
                # Track that this file has been explored
                if file_path != "Unknown":
                    project_context.track_file_exploration(file_path)
                
                output.append(f"\n--- Result {i}: {file_path} (Score: {score:.2f}) ---\n")
                output.append(content)
            
            return "\n".join(output)
        except Exception as e:
            return f"Error searching code: {e}"

    # Use the standard @tool decorator for consistency
    @tool
    def write_file(file_path_content):
        """Write content to a file (requires permission). Format: 'file_path|content'"""
        try:
            # Parse the input
            if '|' in file_path_content:
                # Standard format with pipe separator
                parts = file_path_content.split('|', 1)
                file_path = parts[0].strip()
                content = parts[1] if len(parts) > 1 else ""
            elif '\n' in file_path_content and not file_path_content.startswith('/'):
                # Try to handle format where first line is filename and rest is content
                lines = file_path_content.split('\n', 1)
                file_path = lines[0].strip()
                content = lines[1] if len(lines) > 1 else ""
            else:
                # Assume it's just a file path with empty content
                file_path = file_path_content.strip()
                content = ""

            # Check permission
            if not perm_manager.check_permission("write", file_path):
                perm_granted = perm_manager.request_permission(
                    "write",
                    f"Write to file: {file_path}",
                    "This will modify your filesystem."
                )

                if not perm_granted:
                    return "Permission denied: Cannot write to file"

            # Write file
            full_path = project_context.project_dir / file_path

            # Create parent directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            full_path.write_text(content)

            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}."

    @tool
    def respond(message):
        """Send a text response directly to the user."""
        # This tool simply returns the message, which will be displayed to the user
        return message

    # Create the tools list
    tools = [list_files, read_file, search_code, write_file, respond]

    # Return all tools - use the standard @tool decorated function
    return tools