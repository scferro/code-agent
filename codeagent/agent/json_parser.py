"""JSON response parser for CodeAgent."""
import json
import re
from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class JsonResponseParser:
    """Parse JSON responses from the model into action and parameters."""
    
    def __init__(self):
        """Initialize the parser."""
        # Regex pattern to extract JSON from response
        self.json_pattern = r'```json\s*(.*?)\s*```|(\{.*\})'
    
    def parse(self, response: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse the model response to extract action and parameters.
        
        Args:
            response: The raw response from the model
            
        Returns:
            Tuple of (action_name, parameters_dict)
            
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
            
            # Extract action and parameters
            if 'action' not in parsed:
                raise ValueError("Response JSON must contain an 'action' field")

            action = parsed['action']

            # First try 'parameters' field (our JSON schema)
            params = parsed.get('parameters', {})

            # If parameters is empty, check for 'action_input' (LangChain format)
            if not params and 'action_input' in parsed:
                action_input = parsed['action_input']

                # For write_file, handle the pipe-separated format
                if action == 'write_file' and isinstance(action_input, str):
                    params = {'file_path_content': action_input}
                # For list_files, handle the directory parameter
                elif action == 'list_files' and isinstance(action_input, str):
                    params = {'directory': action_input}
                # For read_file, handle the file_path parameter
                elif action == 'read_file' and isinstance(action_input, str):
                    params = {'file_path': action_input}
                # For search_code, handle the query parameter
                elif action == 'search_code' and isinstance(action_input, str):
                    params = {'query': action_input}
                # For respond, handle the message parameter
                elif action == 'respond' and isinstance(action_input, str):
                    params = {'message': action_input}
                # Generic fallback for other tools
                else:
                    params = {'input': action_input}

            return action, params
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            # Default to "respond" action with the original text
            return "respond", {"message": response}
    
    def format_for_agent(self, action: str, params: Dict[str, Any]) -> str:
        """
        Format the action and parameters as a string for display.
        
        Args:
            action: The action name
            params: The parameters dictionary
            
        Returns:
            A formatted string describing the action
        """
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"{action}({params_str})"