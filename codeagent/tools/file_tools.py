"""File operation tools"""
from langchain.tools import tool

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

                            # Mark this directory as explored in the project context
                            project_context.explored_dirs.add(str(rel_path))

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

            # We don't call track_dir_exploration directly here anymore
            # It's now handled by action_executor.py which passes the conversation_state correctly

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
            
            # We don't call track_file_exploration directly here anymore
            # It's now handled by action_executor.py which passes the conversation_state correctly
            
            # Return formatted content
            separator = "=" * len(file_info)
            return f"{file_info}\n{separator}\n\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"

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
    def final_answer(message):
        """Signal that the task is complete and end your turn."""
        # This tool marks the task as complete and returns a final message
        return message

    @tool
    def update_file(file_path, old_text, new_text):
        """Update a file by replacing specified text with new text.
        
        Args:
            file_path: The path to the file to update
            old_text: The text to replace
            new_text: The new text to insert
        """
        try:
            full_path = project_context.project_dir / file_path
            
            # Check if file exists
            if not full_path.exists():
                return f"Error: File '{file_path}' does not exist"
                
            if not full_path.is_file():
                return f"Error: '{file_path}' is not a file"
            
            # Check permission
            if not perm_manager.check_permission("write", file_path):
                perm_granted = perm_manager.request_permission(
                    "write",
                    f"Update file: {file_path}",
                    "This will modify your filesystem."
                )

                if not perm_granted:
                    return "Permission denied: Cannot update file"
            
            # Read the current content
            content = full_path.read_text(errors='ignore')
            
            # Check if the old_text exists in the file
            if old_text not in content:
                return f"Error: The text to replace was not found in {file_path}."
            
            # Replace the text
            new_content = content.replace(old_text, new_text)
            
            # Write the updated content
            full_path.write_text(new_content)
            
            # Track that this file has been explored and modified
            project_context.track_file_exploration(file_path)
            
            return f"Successfully updated {file_path}"
        except Exception as e:
            return f"Error updating file: {str(e)}."

    # Create the tools list
    tools = [list_files, read_file, write_file, update_file, final_answer]

    # Return all tools - use the standard @tool decorated function
    return tools