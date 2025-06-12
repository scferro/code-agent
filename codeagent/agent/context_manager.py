"""Context manager for intelligent file context management."""
from typing import Dict, List, Optional, Any
from pathlib import Path


class ContextManager:
    """Manages file context with smart size limits and eviction."""
    
    def __init__(self, conversation_state, project_context, llm=None):
        """Initialize the context manager.
        
        Args:
            conversation_state: ConversationState instance
            project_context: ProjectContext instance  
            llm: Optional LLM instance for file summarization
        """
        self.conversation_state = conversation_state
        self.project_context = project_context
        self.llm = llm
        
        # Set back-reference so conversation_state can access this manager
        self.conversation_state.context_manager = self
    
    def update_file_context(self, file_path: str, content: str, access_type: str = 'read') -> None:
        """Update file context with smart management.
        
        Args:
            file_path: Path to the file
            content: File content
            access_type: Type of access ('read', 'write', 'edit')
        """
        # Don't add forgotten files
        if file_path in self.conversation_state.forgotten_files:
            return
        
        # Add to active context
        self.conversation_state.add_active_file(file_path, content, access_type)
        
        # Check if we need to enforce limits
        if not self.conversation_state.check_context_size_limit():
            self.enforce_context_limits()
    
    def summarize_file_content(self, file_path: str, content: str) -> str:
        """Generate a summary of file content.
        
        Args:
            file_path: Path to the file
            content: File content to summarize
            
        Returns:
            Summary of the file content
        """
        if not self.llm:
            # Fallback: simple summary without LLM
            return self._create_simple_summary(file_path, content)
        
        try:
            # Use LLM to create intelligent summary
            summary_prompt = f"""Please create a concise summary of this code file that preserves the most important information for future reference.

File: {file_path}

Focus on:
- Main purpose/functionality
- Key classes and functions
- Important imports and dependencies
- Notable patterns or architecture decisions

Keep it under 500 characters while retaining essential details.

File content:
{content}"""
            
            response = self.llm.invoke(summary_prompt)
            summary = response.content if hasattr(response, 'content') else str(response)
            
            # Ensure summary isn't too long
            if len(summary) > 500:
                summary = summary[:497] + "..."
            
            return summary
            
        except Exception as e:
            # Fallback to simple summary if LLM fails
            return self._create_simple_summary(file_path, content)
    
    def _create_simple_summary(self, file_path: str, content: str) -> str:
        """Create a simple summary without LLM.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            Simple summary of the file
        """
        lines = content.split('\n')
        file_ext = Path(file_path).suffix
        
        summary_parts = [f"File: {file_path} ({len(lines)} lines)"]
        
        # Extract key information based on file type
        if file_ext == '.py':
            # Python file analysis
            imports = [line.strip() for line in lines if line.strip().startswith(('import ', 'from '))]
            classes = [line.strip() for line in lines if line.strip().startswith('class ')]
            functions = [line.strip() for line in lines if line.strip().startswith('def ')]
            
            if imports:
                summary_parts.append(f"Imports: {', '.join(imports[:3])}")
            if classes:
                summary_parts.append(f"Classes: {', '.join([c.split(':')[0] for c in classes[:3]])}")
            if functions:
                summary_parts.append(f"Functions: {', '.join([f.split('(')[0].replace('def ', '') for f in functions[:5]])}")
        
        elif file_ext in ['.js', '.ts']:
            # JavaScript/TypeScript file analysis
            imports = [line.strip() for line in lines if 'import' in line and 'from' in line]
            functions = [line.strip() for line in lines if line.strip().startswith(('function ', 'const ', 'let ', 'var ')) and '=>' in line or '= function' in line]
            
            if imports:
                summary_parts.append(f"Imports: {len(imports)} modules")
            if functions:
                summary_parts.append(f"Functions: {len(functions)} defined")
        
        # Add docstring or first comment if available
        for line in lines[:10]:
            if line.strip().startswith(('"""', "'''", '//', '#')):
                doc = line.strip().strip('"""\'/#').strip()
                if doc and len(doc) > 10:
                    summary_parts.append(f"Purpose: {doc[:100]}")
                    break
        
        summary = "; ".join(summary_parts)
        
        # Ensure it's not too long
        if len(summary) > 400:
            summary = summary[:397] + "..."
        
        return summary
    
    def enforce_context_limits(self) -> List[str]:
        """Enforce context size limits by evicting old files.
        
        Returns:
            List of file paths that were evicted
        """
        if self.conversation_state.check_context_size_limit():
            return []
        
        # Target 80% of max size to give some breathing room
        target_size = int(self.conversation_state.max_context_size * 0.8)
        
        evicted = self.conversation_state.evict_oldest_files(target_size)
        
        return evicted
    
    def build_smart_context_string(self) -> str:
        """Build a smart context string for prompts.
        
        Returns:
            Formatted context string with active and explored files
        """
        if not self.conversation_state.active_files and not self.conversation_state.explored_files:
            return "No code files have been accessed yet."
        
        result = []
        
        # Active files section (full content)
        if self.conversation_state.active_files:
            result.append("=== ACTIVE FILES (Full Content) ===")
            
            for file_path, file_info in self.conversation_state.active_files.items():
                pin_indicator = " 📌" if file_info.is_pinned else ""
                access_info = f" (accessed {file_info.access_count}x, last: {file_info.access_type})"
                
                result.append(f"--- {file_path}{pin_indicator}{access_info} ---")
                result.append(file_info.content)
                result.append("")  # Empty line for separation
        
        # Explored files section (summaries only)
        if self.conversation_state.explored_files:
            result.append("=== EXPLORED FILES (Summaries) ===")
            
            for file_path, file_info in self.conversation_state.explored_files.items():
                access_info = f" (accessed {file_info.access_count}x)"
                result.append(f"📄 {file_path}{access_info}")
                
                if file_info.summary:
                    result.append(f"   Summary: {file_info.summary}")
                else:
                    result.append(f"   Size: {file_info.size_bytes} bytes")
                result.append("")
        
        # Context statistics
        stats = self.conversation_state.get_context_summary()
        result.append("=== CONTEXT STATS ===")
        result.append(f"Size: {stats['total_size_bytes']:,} / {stats['max_size_bytes']:,} bytes ({stats['size_percentage']:.1f}%)")
        result.append(f"Active: {stats['active_files_count']}, Explored: {stats['explored_files_count']}, Pinned: {stats['pinned_files_count']}")
        
        if stats['pinned_files']:
            result.append(f"Pinned files: {', '.join(stats['pinned_files'])}")
        
        return "\n".join(result)
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get detailed context statistics.
        
        Returns:
            Dictionary with context statistics
        """
        return self.conversation_state.get_context_summary()
    
    def migrate_legacy_context(self) -> None:
        """Migrate existing code_context to new system.
        
        This helps transition from the old simple context to smart context.
        """
        for file_path, content in self.conversation_state.code_context.items():
            if file_path not in self.conversation_state.active_files and file_path not in self.conversation_state.explored_files:
                # Add to active context but don't trigger size checks yet
                from codeagent.agent.conversation_state import FileContextInfo
                self.conversation_state.active_files[file_path] = FileContextInfo(
                    path=file_path,
                    content=content,
                    access_type='read'
                )
                
                # Update LRU tracking
                if file_path not in self.conversation_state.file_access_order:
                    self.conversation_state.file_access_order.append(file_path)
        
        # Update context size after migration
        self.conversation_state._update_context_size()
        
        # Enforce limits if needed
        if not self.conversation_state.check_context_size_limit():
            self.enforce_context_limits()