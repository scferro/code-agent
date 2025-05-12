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
    
    def track_file_exploration(self, file_path: str):
        """Track that a file has been explored"""
        self.explored_files.add(file_path)
    
    def track_dir_exploration(self, dir_path: str):
        """Track that a directory has been explored"""
        self.explored_dirs.add(dir_path)
    
    def has_been_explored(self, path: str) -> bool:
        """Check if a file or directory has been explored"""
        return path in self.explored_files or path in self.explored_dirs