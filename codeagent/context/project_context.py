"""Project context management"""
from pathlib import Path
import os
import time
from typing import List, Dict, Any, Optional, Set, Tuple

from codeagent.context.agent_md import AgentMdParser
from codeagent.context.embeddings import CodeEmbedder

class ProjectContext:
    """Manages project context and understanding"""
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).absolute()
        
        # Cache directory
        self.cache_dir = self.project_dir / ".codeagent"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Agent.md parser for static context
        self.agent_md_parser = AgentMdParser()
        self.static_context = self._load_static_context()
        
        # Code embedder for semantic search
        self.code_embedder = CodeEmbedder(cache_dir=self.cache_dir)
        
        # Track explored files and directories
        self.explored_files: Set[str] = set()
        self.explored_dirs: Set[str] = set()
        
        # Lazy-loaded embedding index
        self._vector_store = None
    
    def _load_static_context(self) -> Dict[str, Any]:
        """Load static context from .agent.md files"""
        # Define paths to check in order of precedence (later overrides earlier)
        context_paths = [
            Path.home() / ".agent.md",  # Global settings
            self.project_dir / ".agent.md",  # Project settings
            self.project_dir / ".agent.local.md"  # Local settings
        ]
        
        # Load and merge context
        return self.agent_md_parser.load_context(context_paths)
    
    def get_static_context_summary(self) -> str:
        """Get a summary of the static context for prompts"""
        if not self.static_context:
            return "No project-specific information available."
        
        summary = []
        
        # Project description
        if self.static_context.get("project_description"):
            summary.append(f"Project Description: {self.static_context['project_description']}")
        
        # Architecture
        if self.static_context.get("architecture"):
            summary.append(f"Architecture: {self.static_context['architecture']}")
        
        # Code style
        if self.static_context.get("code_style"):
            summary.append(f"Code Style: {self.static_context['code_style']}")
        
        # Common commands
        if self.static_context.get("common_commands"):
            cmd_str = ", ".join([f"{k}: `{v}`" for k, v in self.static_context["common_commands"].items()])
            if cmd_str:
                summary.append(f"Common Commands: {cmd_str}")
        
        # File descriptions (summarized)
        if self.static_context.get("file_descriptions"):
            file_count = len(self.static_context["file_descriptions"])
            if file_count > 0:
                summary.append(f"File Descriptions: {file_count} file(s) documented in .agent.md")
        
        return "\n".join(summary)
    
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
    
    def get_vector_store(self):
        """Get vector store (lazy loading)"""
        if self._vector_store is None:
            self._vector_store = self.code_embedder.embed_codebase(
                self.project_dir,
                exclude_dirs=[".git", "node_modules", "venv", "__pycache__", ".codeagent"]
            )
        return self._vector_store
    
    def search_code(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search code using semantic search"""
        # Ensure vector store is loaded
        self.get_vector_store()
        
        # Search using the embedder
        return self.code_embedder.search(query, top_k=top_k)
    
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