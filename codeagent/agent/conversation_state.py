"""Conversation state management for multi-round interactions."""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from datetime import datetime

class AgentType(Enum):
    """Enum for different agent types."""
    MAIN = "main"
    SUB = "sub"


@dataclass
class FileContextInfo:
    """Information about a file in the context."""
    path: str
    content: str
    summary: str = ""
    size_bytes: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    access_type: str = "read"  # 'read', 'write', 'edit'
    is_pinned: bool = False
    is_summarized: bool = False
    
    def __post_init__(self):
        """Calculate size_bytes if not provided."""
        if self.size_bytes == 0:
            self.size_bytes = len(self.content.encode('utf-8'))
    
    def update_access(self, access_type: str = "read"):
        """Update access information."""
        self.last_accessed = datetime.now()
        self.access_count += 1
        self.access_type = access_type


@dataclass
class ConversationState:
    """Tracks the state of a conversation with action sequences."""

    # The current user's message
    current_user_message: str = ""

    # History of user and assistant messages, excluding action results
    message_history: List[Dict[str, Any]] = field(default_factory=list)

    # History of action results from previous turns
    action_history: List[Dict[str, Any]] = field(default_factory=list)

    # Only the most recent action result
    latest_action_result: Optional[Dict[str, Any]] = None

    # Results from the most recent action sequence
    current_action_results: List[Dict[str, Any]] = field(default_factory=list)

    # Current state of the conversation
    state: str = "awaiting_user_input"

    # Turn counter for tracking conversation progress
    turn_count: int = 0

    # Task metadata for storing information
    task_metadata: Dict[str, Any] = field(default_factory=dict)

    # Flag to indicate whether the task is complete
    task_complete: bool = False

    # Set of explored directories
    explored_directories: Set[str] = field(default_factory=set)

    # File system context - directory tree structure
    file_system_context: Dict[str, Any] = field(default_factory=dict)

    # Code context - maps file paths to content
    code_context: Dict[str, str] = field(default_factory=dict)
    
    # Current active agent
    current_agent: AgentType = AgentType.MAIN
    
    # Dictionary mapping agent types to their respective state information
    agent_states: Dict[AgentType, Dict[str, Any]] = field(default_factory=lambda: {
        AgentType.MAIN: {"messages": [], "actions": []},
        AgentType.SUB: {"messages": [], "actions": []}
    })
    
    # New context management fields
    active_files: Dict[str, FileContextInfo] = field(default_factory=dict)
    explored_files: Dict[str, FileContextInfo] = field(default_factory=dict)
    context_size_bytes: int = 0
    max_context_size: int = 100000  # ~100KB limit
    file_access_order: List[str] = field(default_factory=list)  # LRU tracking
    pinned_files: Set[str] = field(default_factory=set)
    forgotten_files: Set[str] = field(default_factory=set)
    context_manager: Optional[Any] = None  # Will be set to ContextManager instance
    
    # Todo list for task management (simple string format like Claude Code)
    todo_list: List[str] = field(default_factory=list)
    
    def add_user_message(self, message: str) -> None:
        """Add a user message to the history.
        
        Args:
            message: The user's message
        """
        self.current_user_message = message
        self.message_history.append({
            "role": "user",
            "content": message
        })
        self.state = "awaiting_agent_response"
    
    def add_assistant_message(self, message: str) -> None:
        """Add an assistant message to the history.
        
        Args:
            message: The assistant's message
        """
        self.message_history.append({
            "role": "assistant",
            "content": message
        })
    
    def add_action_results(self, results: List[Dict[str, Any]]) -> None:
        """Add action results to the history.

        Args:
            results: List of action result dictionaries
        """
        self.current_action_results = results
        self.action_history.extend(results)

        # Store only the most recent result for prompt display
        if results:
            self.latest_action_result = results[-1]

        self.state = "awaiting_further_actions"
    
    def is_final_response(self, actions: List[Dict[str, Any]]) -> bool:
        """Check if this is a terminal response.

        Args:
            actions: List of action dictionaries

        Returns:
            True if this is a terminal response ONLY if final_answer is present
        """
        # Check if the task has been marked as complete
        if self.task_complete:
            return True

        # ONLY check for final_answer action - this is the only way to end a turn
        for action in actions:
            if action.get("action") == "final_answer":
                return True

        # All other responses should continue the conversation
        return False
    
    def should_continue_action_sequence(self) -> bool:
        """Check if we should continue the current action sequence.

        Returns:
            True if we should request further actions from the model
        """
        # Only continue if we're in the awaiting_further_actions state
        return self.state == "awaiting_further_actions"

    def store_task_data(self, key: str, value: Any) -> None:
        """Store data in the task metadata dictionary.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        self.task_metadata[key] = value

    def get_task_data(self, key: str, default: Any = None) -> Any:
        """Get data from the task metadata dictionary.

        Args:
            key: The key to retrieve
            default: Default value if key not found

        Returns:
            The stored value or default if not found
        """
        return self.task_metadata.get(key, default)

    def reset_task(self) -> None:
        """Reset task-related state for a new task."""
        self.task_metadata = {}
        self.task_complete = False

    def mark_task_complete(self) -> None:
        """Mark the current task as complete."""
        self.task_complete = True

    def is_task_complete(self) -> bool:
        """Check if the current task is complete."""
        return self.task_complete

    def mark_directory_explored(self, path: str) -> None:
        """Mark a directory as explored.

        Args:
            path: The path to the directory that has been explored
        """
        self.explored_directories.add(path)

    def update_file_system_context(self, path: str, structure: Dict[str, Any]) -> None:
        """Update file system context with new directory structure.

        Args:
            path: The path to the directory
            structure: The directory structure data
        """
        self.file_system_context[path] = structure

    def update_code_context(self, file_path: str, content: str) -> None:
        """Update code context with file content.

        Args:
            file_path: The path to the file
            content: The content of the file
        """
        self.code_context[file_path] = content

    def get_file_system_context_string(self) -> str:
        """Get file system context as a formatted string for the prompt.

        Returns:
            A formatted string representation of the file system context
        """
        if not self.file_system_context:
            return "No directories have been explored yet."

        # Format the directory structure as a string
        result = []
        for path, structure in self.file_system_context.items():
            if isinstance(structure, dict) and "children" in structure:
                result.append(f"📁 {path}/")
                for child in structure.get("children", []):
                    prefix = "    "
                    if child.get("type") == "directory":
                        result.append(f"{prefix}📁 {child.get('name', '')}/")
                    else:
                        result.append(f"{prefix}📄 {child.get('name', '')}")

        return "\n".join(result) if result else "No file system structure available."

    def get_code_context_string(self) -> str:
        """Get code context as a formatted string for the prompt.

        Returns:
            A formatted string representation of the code context
        """
        if not self.code_context:
            return "No code files have been accessed yet."

        result = []
        for file_path, content in self.code_context.items():
            result.append(f"=== {file_path} ===")
            result.append(content)
            result.append("")  # Empty line for separation

        return "\n".join(result)

    def reset_task(self) -> None:
        """Reset task-related state for a new task."""
        self.task_metadata = {}
        self.task_complete = False
        # Don't reset file_system_context and code_context to maintain context across tasks
        
    def store_agent_state(self) -> None:
        """Store the current agent's state."""
        # Store current messages and actions to the agent's state
        self.agent_states[self.current_agent] = {
            "messages": deepcopy(self.message_history),
            "actions": deepcopy(self.action_history),
            "latest_result": deepcopy(self.latest_action_result),
            "current_results": deepcopy(self.current_action_results),
            "state": self.state
        }
    
    def switch_agent(self, agent_type: AgentType) -> None:
        """Switch to a different agent and restore its state.
        
        Args:
            agent_type: The agent type to switch to
        """
        # Store current agent state before switching
        self.store_agent_state()
        
        # Update current agent
        self.current_agent = agent_type
        
        # Restore state from the agent's saved state
        agent_state = self.agent_states.get(agent_type, {})
        
        # For sub-agents, we maintain file_system_context and code_context,
        # but we reset their message and action history
        if agent_type == AgentType.SUB:
            # Sub-agent gets clean conversation and action history but shares file context
            self.message_history = []
            self.action_history = []
            self.latest_action_result = None
            self.current_action_results = []
            self.state = "awaiting_user_input"
        else:
            # For main agent, restore full state
            self.message_history = deepcopy(agent_state.get("messages", self.message_history))
            self.action_history = deepcopy(agent_state.get("actions", self.action_history))
            self.latest_action_result = deepcopy(agent_state.get("latest_result", self.latest_action_result))
            self.current_action_results = deepcopy(agent_state.get("current_results", self.current_action_results))
            self.state = agent_state.get("state", self.state)
    
    def get_current_agent_type(self) -> str:
        """Get the current agent type as a string.
        
        Returns:
            The current agent type string
        """
        return self.current_agent.value
    
    # New context management methods
    def add_active_file(self, file_path: str, content: str, access_type: str = 'read') -> None:
        """Add a file to active context with smart management.
        
        Args:
            file_path: Path to the file
            content: File content
            access_type: Type of access ('read', 'write', 'edit')
        """
        # Remove from explored if it was there
        if file_path in self.explored_files:
            del self.explored_files[file_path]
        
        # Create or update file info
        if file_path in self.active_files:
            self.active_files[file_path].content = content
            self.active_files[file_path].update_access(access_type)
        else:
            self.active_files[file_path] = FileContextInfo(
                path=file_path,
                content=content,
                access_type=access_type,
                is_pinned=file_path in self.pinned_files
            )
        
        # Update LRU tracking
        if file_path in self.file_access_order:
            self.file_access_order.remove(file_path)
        self.file_access_order.append(file_path)
        
        # Update context size
        self._update_context_size()
        
        # Also update legacy code_context for backward compatibility
        self.code_context[file_path] = content
    
    def move_to_explored(self, file_path: str) -> None:
        """Move a file from active to explored context.
        
        Args:
            file_path: Path to the file to move
        """
        if file_path in self.active_files and not self.active_files[file_path].is_pinned:
            file_info = self.active_files[file_path]
            
            # Generate summary if not already done
            if not file_info.is_summarized and self.context_manager:
                file_info.summary = self.context_manager.summarize_file_content(file_path, file_info.content)
                file_info.is_summarized = True
            
            # Move to explored
            self.explored_files[file_path] = file_info
            del self.active_files[file_path]
            
            # Remove from legacy code_context
            if file_path in self.code_context:
                del self.code_context[file_path]
            
            # Update context size
            self._update_context_size()
    
    def pin_file(self, file_path: str) -> bool:
        """Pin a file to keep it in active context.
        
        Args:
            file_path: Path to the file to pin
            
        Returns:
            True if file was pinned, False if not found
        """
        self.pinned_files.add(file_path)
        
        # If file is in active context, mark it as pinned
        if file_path in self.active_files:
            self.active_files[file_path].is_pinned = True
            return True
        
        # If file is in explored context, move it back to active
        if file_path in self.explored_files:
            file_info = self.explored_files[file_path]
            file_info.is_pinned = True
            self.active_files[file_path] = file_info
            del self.explored_files[file_path]
            
            # Add back to legacy code_context
            self.code_context[file_path] = file_info.content
            
            # Update LRU tracking
            if file_path in self.file_access_order:
                self.file_access_order.remove(file_path)
            self.file_access_order.append(file_path)
            
            self._update_context_size()
            return True
        
        return False
    
    def forget_file(self, file_path: str) -> bool:
        """Remove a file from context entirely.
        
        Args:
            file_path: Path to the file to forget
            
        Returns:
            True if file was removed, False if not found
        """
        self.forgotten_files.add(file_path)
        self.pinned_files.discard(file_path)
        
        removed = False
        
        if file_path in self.active_files:
            del self.active_files[file_path]
            removed = True
        
        if file_path in self.explored_files:
            del self.explored_files[file_path]
            removed = True
        
        if file_path in self.code_context:
            del self.code_context[file_path]
        
        if file_path in self.file_access_order:
            self.file_access_order.remove(file_path)
        
        if removed:
            self._update_context_size()
        
        return removed
    
    def check_context_size_limit(self) -> bool:
        """Check if context size is within limits.
        
        Returns:
            True if within limits, False if over limit
        """
        return self.context_size_bytes <= self.max_context_size
    
    def evict_oldest_files(self, target_size: int) -> List[str]:
        """Evict oldest unpinned files to reach target size.
        
        Args:
            target_size: Target context size in bytes
            
        Returns:
            List of file paths that were evicted
        """
        evicted = []
        
        # Start from oldest files (beginning of access order)
        for file_path in self.file_access_order[:]:
            if self.context_size_bytes <= target_size:
                break
            
            if (file_path in self.active_files and 
                not self.active_files[file_path].is_pinned):
                self.move_to_explored(file_path)
                evicted.append(file_path)
        
        return evicted
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of current context usage.
        
        Returns:
            Dictionary with context statistics
        """
        return {
            "total_size_bytes": self.context_size_bytes,
            "max_size_bytes": self.max_context_size,
            "size_percentage": (self.context_size_bytes / self.max_context_size) * 100,
            "active_files_count": len(self.active_files),
            "explored_files_count": len(self.explored_files),
            "pinned_files_count": len(self.pinned_files),
            "active_files": list(self.active_files.keys()),
            "pinned_files": list(self.pinned_files),
            "within_limits": self.check_context_size_limit()
        }
    
    def _update_context_size(self) -> None:
        """Update the total context size calculation."""
        total_size = 0
        
        # Count active files (full content)
        for file_info in self.active_files.values():
            total_size += file_info.size_bytes
        
        # Count explored files (summaries only)
        for file_info in self.explored_files.values():
            if file_info.summary:
                total_size += len(file_info.summary.encode('utf-8'))
        
        self.context_size_bytes = total_size
    
    def update_todo_list(self, todo_list: List[str]) -> None:
        """Update the todo list with new todos.
        
        Args:
            todo_list: List of todo strings in Claude Code format (☐/☒ bullets)
        """
        self.todo_list = todo_list
    
    def get_todo_list_string(self) -> str:
        """Get todo list as a formatted string for the prompt.
        
        Returns:
            A formatted string representation of the todo list
        """
        if not self.todo_list:
            return "No todos currently tracked."
        
        return "\n".join(self.todo_list)