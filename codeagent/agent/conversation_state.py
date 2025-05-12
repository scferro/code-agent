"""Conversation state management for multi-round interactions."""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    """Tracks the state of a conversation with action sequences."""

    # The current user's message
    current_user_message: str = ""

    # History of user and assistant messages, excluding action results
    message_history: List[Dict[str, Any]] = field(default_factory=list)

    # History of action results from previous turns
    action_history: List[Dict[str, Any]] = field(default_factory=list)

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
        self.state = "awaiting_further_actions"
    
    def is_final_response(self, actions: List[Dict[str, Any]]) -> bool:
        """Check if this is a terminal response.

        Args:
            actions: List of action dictionaries

        Returns:
            True if this is a terminal response ONLY if end_turn is present
        """
        # Check if the task has been marked as complete
        if self.task_complete:
            return True

        # ONLY check for end_turn action - this is the only way to end a turn
        for action in actions:
            if action.get("action") == "end_turn":
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