"""JSON response parser for CodeAgent."""
import json
import re
from typing import Dict, Any, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

class JsonResponseParser:
    """Parse JSON responses from the model into sequences of actions."""
    
    def __init__(self):
        """Initialize the parser."""
        # Regex pattern to extract JSON from response
        self.json_pattern = r'```json\s*(.*?)\s*```|(\{.*\})'
    
    def parse(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse the model response to extract a sequence of actions.
        
        Args:
            response: The raw response from the model
            
        Returns:
            List of action dictionaries with 'action' and 'parameters' keys
            
        Raises:
            ValueError: If the response doesn't contain valid JSON or required fields
        """
        try:
            # Extract JSON from response (handling both raw JSON and markdown-formatted JSON)
            json_match = re.search(self.json_pattern, response, re.DOTALL)
            
            if json_match:
                # Get the matched group (either the JSON in code block or raw JSON)
                json_str = json_match.group(1) if json_match.group(1) else json_match.group(2)
                parsed = json.loads(json_str)
            else:
                # Try to parse the entire response as JSON
                parsed = json.loads(response)
            
            # Check if the response uses the actions array format
            if 'actions' in parsed:
                return self._parse_actions_array(parsed['actions'])
            
            # Legacy format: check for single action
            if 'action' in parsed:
                return [self._parse_single_action(parsed)]
            
            # If no recognized format, treat as plain text response
            return [{
                "action": "respond",
                "parameters": {"message": "I couldn't parse the model's response properly. Please try again."}
            }]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Default to "respond" action with the original text
            return [{
                "action": "respond",
                "parameters": {"message": response}
            }]
    
    def _parse_actions_array(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse an array of actions from the model response.
        
        Args:
            actions: List of action dictionaries from the model
            
        Returns:
            Processed list of action dictionaries
        """
        result = []
        
        for action_data in actions:
            if not isinstance(action_data, dict):
                continue
                
            if 'action' not in action_data:
                continue
                
            parsed_action = self._parse_single_action(action_data)
            result.append(parsed_action)
        
        # Validate that the first action is 'respond' or insert one if missing
        if not result or result[0]["action"] != "respond":
            # Insert a default respond action at the beginning
            result.insert(0, {
                "action": "respond",
                "parameters": {"message": "I'm analyzing your request..."}
            })
        
        return result
    
    def _parse_single_action(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a single action from the model response.
        
        Args:
            action_data: Dictionary containing action data
            
        Returns:
            Processed action dictionary
        """
        action = action_data['action']
        
        # First try 'parameters' field (our JSON schema)
        params = action_data.get('parameters', {})
        
        # If parameters is empty, check for 'action_input'
        if not params and 'action_input' in action_data:
            params = action_data.get('action_input', {})
        
        return {
            "action": action,
            "parameters": params,
            "original_parameters": params.copy() if params else {}
        }
    
    def format_for_agent(self, actions: List[Dict[str, Any]]) -> str:
        """
        Format the action sequence as a string for display.
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            A formatted string describing the actions
        """
        if not actions:
            return "No actions"
            
        formatted = []
        for i, action in enumerate(actions):
            action_name = action["action"]
            params = action["parameters"]
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            formatted.append(f"{i+1}. {action_name}({params_str})")
            
        return "\n".join(formatted)
        
    # For backward compatibility
    def format_single_action(self, action: str, params: Dict[str, Any]) -> str:
        """
        Format a single action and parameters as a string for display.
        
        Args:
            action: The action name
            params: The parameters dictionary
            
        Returns:
            A formatted string describing the action
        """
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"{action}({params_str})"