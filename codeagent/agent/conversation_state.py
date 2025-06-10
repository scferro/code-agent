"""Conversation state management for multi-round interactions."""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

class AgentType(Enum):
    """Enum for different agent types."""
    MASTER = "master"
    CODER = "coder"
    DEEP_THINKER = "deep_thinker"


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
    current_agent: AgentType = AgentType.MASTER
    
    # Dictionary mapping agent types to their respective state information
    agent_states: Dict[AgentType, Dict[str, Any]] = field(default_factory=lambda: {
        AgentType.MASTER: {"messages": [], "actions": []},
        AgentType.CODER: {"messages": [], "actions": []},
        AgentType.DEEP_THINKER: {"messages": [], "actions": []}
    })
    
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
        if agent_type != AgentType.MASTER:
            self.message_history = deepcopy(agent_state.get("messages", []))
            self.action_history = deepcopy(agent_state.get("actions", []))
            self.latest_action_result = deepcopy(agent_state.get("latest_result"))
            self.current_action_results = deepcopy(agent_state.get("current_results", []))
            self.state = agent_state.get("state", "awaiting_user_input")
        else:
            # For master agent, restore full state
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