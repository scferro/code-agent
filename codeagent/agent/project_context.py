"""Project context management"""
from pathlib import Path
import os
import time
from typing import List, Dict, Any, Optional, Set, Tuple

class ProjectContext:
    """Manages project context and understanding"""
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).absolute()
        
        # Cache directory
        self.cache_dir = self.project_dir / ".codeagent"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Track explored files and directories
        self.explored_files: Set[str] = set()
        self.explored_dirs: Set[str] = set()
        
        # Lazy-loaded embedding index
        self._vector_store = None
        
    def get_file_description(self, file_path: str) -> Optional[str]:
        """Get description for a specific file from .agent.md"""
        if not self.static_context.get("file_descriptions"):
            return None
        
        # Try exact match
        if file_path in self.static_context["file_descriptions"]:
            return self.static_context["file_descriptions"][file_path]
        
        # Try with and without leading ./
        if file_path.startswith("./") and file_path[2:] in self.static_context["file_descriptions"]:
            return self.static_context["file_descriptions"][file_path[2:]]
        
        # Check if file_path is a more specific path to a documented directory
        for path, desc in self.static_context["file_descriptions"].items():
            if path.endswith("/") and file_path.startswith(path):
                return f"Part of {path}: {desc}"
        
        return None
    
    def get_file_structure(self, directory: str = ".") -> Dict[str, Any]:
        """Get file structure for a directory"""
        dir_path = self.project_dir / directory
        
        if not dir_path.exists() or not dir_path.is_dir():
            return {"error": f"Directory {directory} not found"}
        
        structure = {"name": directory, "type": "directory", "children": []}
        
        try:
            entries = list(dir_path.iterdir())
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for entry in entries:
                # Skip hidden files
                if entry.name.startswith("."):
                    continue
                
                rel_path = str(entry.relative_to(self.project_dir))
                
                if entry.is_dir():
                    # For directories, just add the name (don't recurse)
                    structure["children"].append({
                        "name": entry.name,
                        "type": "directory",
                        "path": rel_path
                    })
                else:
                    # For files, add metadata
                    size_kb = entry.stat().st_size / 1024
                    
                    if size_kb < 1:
                        size_str = f"{entry.stat().st_size} bytes"
                    else:
                        size_str = f"{size_kb:.1f} KB"
                    
                    structure["children"].append({
                        "name": entry.name,
                        "type": "file",
                        "path": rel_path,
                        "size": size_str,
                        "extension": entry.suffix
                    })
            
            return structure
        except Exception as e:
            return {"error": f"Error getting file structure: {str(e)}"}
    
    def track_file_exploration(self, file_path: str, conversation_state=None):
        """Track that a file has been explored and update conversation state.

        Args:
            file_path: The path to the file that has been explored
            conversation_state: Optional conversation state to update with code context
        """
        self.explored_files.add(file_path)

        # If conversation state is provided, update its code context
        if conversation_state and hasattr(conversation_state, 'update_code_context'):
            try:
                full_path = self.project_dir / file_path
                if full_path.exists() and full_path.is_file():
                    content = full_path.read_text(errors='ignore')
                    conversation_state.update_code_context(file_path, content)

                    # Also mark parent directory as explored
                    parent_dir = str(full_path.parent.relative_to(self.project_dir))
                    if parent_dir:
                        self.track_dir_exploration(parent_dir, conversation_state)
            except Exception as e:
                print(f"Error updating code context: {e}")

    def track_dir_exploration(self, dir_path: str, conversation_state=None, recursive=False, max_depth=3):
        """Track that a directory has been explored and update conversation state.

        Args:
            dir_path: The path to the directory that has been explored
            conversation_state: Optional conversation state to update with file system context
            recursive: Whether subdirectories should also be marked as explored
            max_depth: How many levels of subdirectories to explore when recursive is True
        """
        self.explored_dirs.add(dir_path)

        # If conversation state is provided, mark the directory as explored
        if conversation_state and hasattr(conversation_state, 'mark_directory_explored'):
            conversation_state.mark_directory_explored(dir_path)

            # Update file system context with directory structure
            try:
                # If recursive, we need to build a more comprehensive tree
                if recursive:
                    structure = self.build_directory_tree(dir_path, 0, max_depth)

                    # Also mark subdirectories as explored up to max_depth
                    dir_path_obj = self.project_dir / dir_path
                    if dir_path_obj.exists() and dir_path_obj.is_dir():
                        self._mark_subdirs_explored(dir_path_obj, conversation_state, 1, max_depth)
                else:
                    structure = self.get_file_structure(dir_path)

                conversation_state.update_file_system_context(dir_path, structure)
            except Exception as e:
                print(f"Error updating file system context: {e}")

    def _mark_subdirs_explored(self, dir_path_obj, conversation_state, current_depth, max_depth):
        """Recursively mark subdirectories as explored.

        Args:
            dir_path_obj: Path object to the current directory
            conversation_state: Conversation state to update
            current_depth: Current recursion depth
            max_depth: Maximum depth to explore
        """
        if current_depth > max_depth:
            return

        try:
            for item in dir_path_obj.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    rel_path = str(item.relative_to(self.project_dir))
                    self.explored_dirs.add(rel_path)
                    conversation_state.mark_directory_explored(rel_path)

                    # Recursively mark subdirectories
                    self._mark_subdirs_explored(item, conversation_state, current_depth + 1, max_depth)
        except Exception as e:
            print(f"Error marking subdirectories: {e}")

    def has_been_explored(self, path: str) -> bool:
        """Check if a file or directory has been explored"""
        return path in self.explored_files or path in self.explored_dirs

    def build_directory_tree(self, path: str = ".", depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
        """Build a hierarchical directory tree.

        Args:
            path: The path to start from
            depth: Current depth (used for recursion)
            max_depth: Maximum depth to explore

        Returns:
            A dictionary representing the directory tree
        """
        dir_path = self.project_dir / path

        if not dir_path.exists() or not dir_path.is_dir():
            return {"error": f"Directory {path} not found"}

        node = {
            "name": dir_path.name,
            "path": path,
            "type": "directory",
            "children": []
        }

        if depth >= max_depth:
            node["note"] = "Max depth reached"
            return node

        try:
            entries = list(dir_path.iterdir())
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            for entry in entries:
                # Skip hidden files and directories
                if entry.name.startswith("."):
                    continue

                rel_path = str(entry.relative_to(self.project_dir))

                if entry.is_dir():
                    # Check if this directory has been explored
                    if rel_path in self.explored_dirs:
                        # Recursively build the tree for this directory
                        child_node = self.build_directory_tree(rel_path, depth + 1, max_depth)
                        node["children"].append(child_node)
                    else:
                        # Just add the directory name without details
                        node["children"].append({
                            "name": entry.name,
                            "path": rel_path,
                            "type": "directory",
                            "explored": False
                        })
                else:
                    # Add file with basic metadata
                    size_kb = entry.stat().st_size / 1024
                    if size_kb < 1:
                        size_str = f"{entry.stat().st_size} bytes"
                    else:
                        size_str = f"{size_kb:.1f} KB"

                    node["children"].append({
                        "name": entry.name,
                        "path": rel_path,
                        "type": "file",
                        "size": size_str,
                        "extension": entry.suffix
                    })

            return node
        except Exception as e:
            return {
                "name": dir_path.name,
                "path": path,
                "type": "directory",
                "error": f"Error building tree: {str(e)}"
            }

    def build_full_directory_tree(self, conversation_state=None) -> Dict[str, Any]:
        """Build a complete tree of all explored directories.

        Args:
            conversation_state: Optional conversation state to update

        Returns:
            A dictionary representing the complete directory tree
        """
        root_tree = self.build_directory_tree(".", 0, 10)  # Higher max_depth for full tree

        # If conversation state is provided, update its file system context
        if conversation_state and hasattr(conversation_state, 'update_file_system_context'):
            conversation_state.update_file_system_context(".", root_tree)

        return root_tree

    def format_directory_tree_as_string(self, tree: Dict[str, Any], prefix: str = "") -> str:
        """Format a directory tree as a simple list of file paths.

        Args:
            tree: The directory tree structure
            prefix: Current indentation prefix (used for recursion)

        Returns:
            A formatted string with just the full file paths
        """
        if not tree or not isinstance(tree, dict):
            return "Invalid tree structure"

        result = []

        # Only process files, not directories
        node_type = tree.get("type", "unknown")
        path = tree.get("path", "")

        if node_type == "file":
            # Just add the full file path
            result.append(path)
        elif node_type == "directory":
            # Process children recursively
            for child in tree.get("children", []):
                child_result = self.format_directory_tree_as_string(child, prefix)
                if child_result:
                    result.append(child_result)

        return "\n".join(result)