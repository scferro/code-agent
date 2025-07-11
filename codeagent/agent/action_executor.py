"""Action Executor for sequential processing of model actions."""
from typing import List, Dict, Any, Optional
import json

from rich.console import Console
from codeagent.agent.conversation_state import AgentType
from codeagent.tools.agent_tools import AgentType as ToolAgentType

console = Console()

class ActionExecutor:
    """Executes a sequence of actions from the model's response."""
    
    def __init__(self, tool_map, project_context, debug=False):
        """Initialize the action executor.
        
        Args:
            tool_map: Dictionary mapping action names to tool objects
            project_context: Project context object
            debug: Whether to print debug information
        """
        self.tool_map = tool_map
        self.project_context = project_context
        self.debug = debug
        self.tool_callback = None
    
    def set_tool_callback(self, callback):
        """Set a callback function to be called before tool execution."""
        self.tool_callback = callback
    
    def execute_actions(self, actions: List[Dict[str, Any]], conversation_state=None) -> List[Dict[str, Any]]:
        """Execute a sequence of actions and return their results.

        Args:
            actions: List of action dictionaries with 'action' and 'parameters' keys
            conversation_state: Optional conversation state for special actions

        Returns:
            List of dictionaries with action and result information
        """
        if not actions:
            return [{"action": "respond", "result": "No actions to execute"}]

        # Execute each action in sequence
        results = []

        for action_data in actions:
            action_name = action_data.get("action")
            parameters = action_data.get("parameters", {})

            if self.debug:
                console.print(f"[dim]Executing action: {action_name} with parameters: {parameters}[/dim]")

            # Special case for status_update action
            if action_name == "status_update":
                message = parameters.get("message", "")
                console.print(f"[bold cyan]\nAgent:[/bold cyan] {message}")
                
                # Add the message to conversation history
                if conversation_state:
                    conversation_state.add_assistant_message(message)
                
                # Return result for this action but don't mark task as complete
                results.append({
                    "action": "status_update",
                    "result": "Status update sent to user",
                    "original_parameters": parameters,
                    "message": message
                })
                continue
            
            # Special case for final_answer action
            if action_name == "final_answer" and conversation_state:
                message = parameters.get("message", "Task completed.")
                console.print(f"[bold green]\nAgent:[/bold green] {message}")
                
                # Mark the task as complete in the conversation state
                conversation_state.mark_task_complete()
                
                # Return result for this action
                results.append({
                    "action": "final_answer",
                    "result": "Turn ended successfully",
                    "original_parameters": parameters,
                    "message": message
                })
                continue
            
            # Special case for invoke_agent action
            if action_name == "invoke_agent" and conversation_state:
                agent_type_str = parameters.get("agent_type", "")
                prompt = parameters.get("prompt", "No prompt provided.")
                
                # Only accept "sub_agent" 
                if agent_type_str != "sub_agent":
                    error_msg = f"Invalid agent type: {agent_type_str}. Only 'sub_agent' is supported."
                    console.print(f"[bold red]Error:[/bold red] {error_msg}")
                    results.append({
                        "action": "invoke_agent",
                        "result": f"Error: {error_msg}",
                        "error": True
                    })
                    continue
                
                console.print(f"[bold blue]Delegating task to sub-agent...[/bold blue]")
                
                # Store the current state before switching
                conversation_state.store_agent_state()
                
                # Switch to the sub agent
                conversation_state.switch_agent(AgentType.SUB)
                
                # Store the prompt for the subagent
                conversation_state.store_task_data("subagent_prompt", prompt)
                
                # Return result for this action
                results.append({
                    "action": "invoke_agent",
                    "result": f"Switched to sub-agent",
                    "parameters": parameters
                })
                continue
            
            # Special case for respond_to_master action
            if action_name == "respond_to_master" and conversation_state:
                response = parameters.get("response", "No response provided.")
                
                # Store the current sub-agent's result
                current_agent = conversation_state.current_agent
                conversation_state.store_task_data(f"{current_agent.value}_result", response)
                
                console.print("[bold blue]Sub-agent task completed, returning to main agent...[/bold blue]")
                
                # Store the current state before switching back
                conversation_state.store_agent_state()
                
                # Switch back to the main agent
                conversation_state.switch_agent(AgentType.MAIN)
                
                # Return result for this action
                results.append({
                    "action": "respond_to_master",
                    "result": f"Sub-agent completed task and returned:\n\n{response}",
                    "parameters": parameters
                })
                continue

            # Check if the action exists
            if action_name not in self.tool_map:
                error_msg = f"Unknown action: {action_name}"
                console.print(f"[bold red]Error:[/bold red] {error_msg}")
                results.append({
                    "action": action_name,
                    "result": f"Error: {error_msg}",
                    "error": True
                })
                continue
                
            # Notify callback if registered
            if self.tool_callback and callable(self.tool_callback):
                self.tool_callback(action_name, parameters)
                
            # Get the tool and execute it
            try:
                tool = self.tool_map[action_name]
                
                # Display brief action notification
                action_summary = self._get_action_summary(action_name, parameters)
                console.print(f"[dim][Action]:[/dim] {action_summary}")
                
                # Execute the tool based on its type and parameters
                result = self._execute_tool(tool, action_name, parameters, conversation_state)
                
                # Special handling for manage_todos responses
                if action_name == "manage_todos" and conversation_state:
                    if result.startswith("MANAGE_TODOS:CLEAR"):
                        conversation_state.update_todo_list([])
                        result = "Todo list cleared"
                    elif result.startswith("MANAGE_TODOS:UPDATE:"):
                        todo_data = result[len("MANAGE_TODOS:UPDATE:"):]
                        todo_lines = todo_data.split(';') if todo_data else []
                        conversation_state.update_todo_list(todo_lines)
                        result = f"Updated todo list with {len(todo_lines)} items"
                
                # Add the result to the results list
                result_entry = {
                    "action": action_name,
                    "result": result,
                    "parameters": parameters,  # Store parameters for all actions by default
                    "success": self._is_successful_result(result, action_name)  # Proper success detection
                }
                
                # Check success directly from result (fix the ordering issue)
                is_successful = self._is_successful_result(result, action_name)
                
                # Update context for successful operations
                if conversation_state and is_successful:
                    if action_name == "write_file" and "file_path_content" in parameters:
                        try:
                            file_path_content = parameters["file_path_content"]
                            if '|' in file_path_content:
                                parts = file_path_content.split('|', 1)
                                file_path = parts[0].strip()
                                
                                # Read the actual content from the file to ensure it's current
                                full_path = self.project_context.project_dir / file_path
                                if full_path.exists():
                                    actual_content = full_path.read_text(errors='ignore')
                                    
                                    # Use smart context management if available
                                    if hasattr(conversation_state, 'context_manager') and conversation_state.context_manager:
                                        conversation_state.context_manager.update_file_context(file_path, actual_content, 'write')
                                    else:
                                        # Fallback to legacy context
                                        conversation_state.update_code_context(file_path, actual_content)
                                    
                                    # Also track that this file has been explored
                                    self.project_context.track_file_exploration(file_path, conversation_state)
                        except Exception as e:
                            if self.debug:
                                console.print(f"[dim]Error updating code context for write_file: {str(e)}[/dim]")
                    
                    elif action_name == "update_file" and "file_path" in parameters:
                        try:
                            file_path = parameters["file_path"]
                            
                            # Read the updated content from the file
                            full_path = self.project_context.project_dir / file_path
                            if full_path.exists():
                                updated_content = full_path.read_text(errors='ignore')
                                
                                # Use smart context management if available
                                if hasattr(conversation_state, 'context_manager') and conversation_state.context_manager:
                                    conversation_state.context_manager.update_file_context(file_path, updated_content, 'edit')
                                else:
                                    # Fallback to legacy context
                                    conversation_state.update_code_context(file_path, updated_content)
                                
                                # Also track that this file has been explored
                                self.project_context.track_file_exploration(file_path, conversation_state)
                        except Exception as e:
                            if self.debug:
                                console.print(f"[dim]Error updating code context for update_file: {str(e)}[/dim]")

                    # Track read file operations
                    elif action_name == "read_file" and "file_path" in parameters:
                        file_path = parameters["file_path"]
                        
                        # Handle both single and multiple file reads
                        try:
                            # Handle both single and multiple file reads
                            if ',' in file_path:
                                # Multiple files - process each one
                                paths = [path.strip() for path in file_path.split(',')]
                                for path in paths:
                                    if not path:
                                        continue
                                    
                                    # Read the file content for smart context management
                                    try:
                                        full_path = self.project_context.project_dir / path
                                        if full_path.exists():
                                            content = full_path.read_text(errors='ignore')
                                            
                                            # Use smart context management if available
                                            if hasattr(conversation_state, 'context_manager') and conversation_state.context_manager:
                                                conversation_state.context_manager.update_file_context(path, content, 'read')
                                            else:
                                                # Fallback to legacy context
                                                conversation_state.update_code_context(path, content)
                                            
                                            # Track that this file has been explored
                                            self.project_context.track_file_exploration(path, conversation_state)
                                    except Exception as e:
                                        if self.debug:
                                            console.print(f"[dim]Error processing file {path}: {str(e)}[/dim]")
                            else:
                                # Single file
                                try:
                                    full_path = self.project_context.project_dir / file_path
                                    if full_path.exists():
                                        content = full_path.read_text(errors='ignore')
                                        
                                        # Use smart context management if available
                                        if hasattr(conversation_state, 'context_manager') and conversation_state.context_manager:
                                            conversation_state.context_manager.update_file_context(file_path, content, 'read')
                                        else:
                                            # Fallback to legacy context
                                            conversation_state.update_code_context(file_path, content)
                                        
                                        # Track that this file has been explored
                                        self.project_context.track_file_exploration(file_path, conversation_state)
                                except Exception as e:
                                    if self.debug:
                                        console.print(f"[dim]Error processing file {file_path}: {str(e)}[/dim]")
                        except Exception as e:
                            if self.debug:
                                console.print(f"[dim]Error tracking read_file: {str(e)}[/dim]")

                # Track list_files operations to update file system context
                elif action_name == "list_files" and "directory" in parameters:
                    dir_path = parameters.get("directory", ".")
                    recursive = parameters.get("recursive", False)
                    max_depth = parameters.get("max_depth", 3)

                    # Store the parameters in the result entry so they're available in action history
                    result_entry["parameters"] = parameters

                    # Check success directly from result (fix the ordering issue)
                    is_successful = self._is_successful_result(result, action_name)
                    
                    # Update conversation state if provided and successful
                    if conversation_state and is_successful:
                        try:
                            # Track that this directory has been explored with conversation state
                            self.project_context.track_dir_exploration(
                                dir_path,
                                conversation_state,
                                recursive=recursive,
                                max_depth=max_depth
                            )

                            # Rebuild the full directory tree for all explored directories
                            self.project_context.build_full_directory_tree(conversation_state)
                        except Exception as e:
                            if self.debug:
                                console.print(f"[dim]Error tracking list_files: {str(e)}[/dim]")

                results.append(result_entry)
                
            except Exception as e:
                import traceback
                error_msg = f"Error executing {action_name}: {str(e)}"
                if self.debug:
                    console.print(f"[bold red]Error:[/bold red] {error_msg}")
                    console.print(traceback.format_exc())
                    
                results.append({
                    "action": action_name,
                    "result": error_msg,
                    "error": True
                })
                
        return results
    
    def _execute_tool(self, tool, action_name: str, parameters: Dict[str, Any], conversation_state=None) -> str:
        """Execute a single tool with appropriate parameter handling.

        Args:
            tool: The tool object to execute
            action_name: The name of the action/tool
            parameters: Dictionary of parameters for the tool
            conversation_state: Optional conversation state for tracking context

        Returns:
            String result from the tool execution
        """
        
        # Try multiple approaches for executing the tool
        try:
            # Method 1: Try using invoke with params dict
            if hasattr(tool, 'invoke'):
                return tool.invoke(parameters)
                
        except Exception as e1:
            if self.debug:
                console.print(f"[dim]Invoke failed: {str(e1)}[/dim]")
                
            try:
                # Method 2: Try using run with the primary parameter value
                if len(parameters) == 1:
                    param_name = next(iter(parameters.keys()))
                    param_value = parameters[param_name]
                    return tool.run(param_value)
                else:
                    # Method 3: Try using run with JSON string
                    tool_input = json.dumps(parameters)
                    return tool.run(tool_input)
                    
            except Exception as e2:
                if self.debug:
                    console.print(f"[dim]Run failed: {str(e2)}[/dim]")
                    
                try:
                    # Method 4: Try direct call as function
                    if len(parameters) == 1:
                        param_value = next(iter(parameters.values()))
                        return tool(param_value)
                    else:
                        return tool(**parameters)
                        
                except Exception as e3:
                    raise Exception(f"All execution methods failed: {str(e3)}")
    
    def _is_successful_result(self, result: Any, action_name: str) -> bool:
        """Determine if an action result indicates success.
        
        Args:
            result: The result from the tool execution
            action_name: The name of the action
            
        Returns:
            True if the result indicates success, False otherwise
        """
        if not isinstance(result, str):
            return True  # Assume non-string results are successful
        
        # Check for common error patterns
        error_indicators = [
            "Error:", "error:", "ERROR:",
            "Failed:", "failed:", "FAILED:",
            "Permission denied:",
            "does not exist",
            "is not a file",
            "is not a directory"
        ]
        
        for indicator in error_indicators:
            if indicator in result:
                return False
        
        # Special cases for specific actions
        if action_name == "read_file":
            # For read_file, success is indicated by content being returned
            # Check for the file info format or multi-file summary
            return ("📚 Read" in result or "File:" in result or "===" in result)
        
        elif action_name in ["write_file", "update_file"]:
            # For write/update operations, look for success message
            return "Successfully" in result
        
        elif action_name == "list_files":
            # For list_files, success is having directory content or empty directory
            return "Directory:" in result
        
        # Default: assume success if no error indicators found
        return True
    
    def _get_action_summary(self, action_name: str, parameters: Dict[str, Any]) -> str:
        """Generate a user-friendly summary of the action being performed.

        Args:
            action_name: The name of the action
            parameters: The parameters for the action

        Returns:
            A short summary string describing the action
        """
        if action_name == "read_file" and "file_path" in parameters:
            return f"Reading {parameters['file_path']}"

        elif action_name == "write_file" and "file_path_content" in parameters:
            file_path = parameters["file_path_content"].split('|', 1)[0].strip()
            return f"Writing to {file_path}"
            
        elif action_name == "update_file" and "file_path" in parameters:
            return f"Updating {parameters['file_path']}"

        elif action_name == "list_files" and "directory" in parameters:
            dir_name = parameters["directory"] or "."
            return f"Listing files in {dir_name}"

        elif action_name == "search_code" and "query" in parameters:
            return f"Searching for '{parameters['query']}'"
            
        elif action_name == "status_update":
            return "Providing status update"
            
        elif action_name == "final_answer":
            return "Ending agent turn"
            
        elif action_name == "invoke_agent" and "agent_type" in parameters:
            return f"Invoking {parameters['agent_type']} agent"
            
        elif action_name == "respond_to_master":
            return "Responding to master agent"

        else:
            # Generic summary
            param_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
            return f"Executing {action_name}({param_str})"