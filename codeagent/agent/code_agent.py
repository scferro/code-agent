"""Main agent class that orchestrates the coding assistant"""
import os
from pathlib import Path

from langchain_ollama import ChatOllama
from langchain.agents import AgentType, initialize_agent

from rich.console import Console

from codeagent.tools.file_tools import get_file_tools
from codeagent.tools.agent_tools import get_agent_tools
from codeagent.agent.project_context import ProjectContext
from codeagent.agent.prompts import (
    get_code_prompt,
    get_action_hist_prompt,
    get_file_system_prompt,
    get_previous_action_prompt,
    get_main_agent_prompt,
    get_sub_agent_prompt
)
from codeagent.agent.json_parser import JsonResponseParser
from codeagent.agent.action_executor import ActionExecutor
from codeagent.agent.conversation_state import ConversationState, AgentType as AgentTypeEnum

console = Console()

class CodeAgent:
    """Main agent class that orchestrates the coding assistant"""

    def __init__(self, project_dir=".", model_name="devstral", verbose=True, debug=False, agent_type=None):
        self.project_dir = Path(project_dir).absolute()
        self.model_name = model_name
        self.verbose = verbose
        self.debug = debug
        self.tool_callback = None
        self._initialized = True
        
        # Set the agent type (default to MAIN if not specified)
        self.agent_type = agent_type if agent_type else AgentTypeEnum.MAIN

        # Initialize context
        self.project_context = ProjectContext(project_dir)

        # Initialize JSON parser and state management
        self.json_parser = JsonResponseParser()
        self.conversation_state = ConversationState()
        
        # Set the initial agent type in the conversation state
        self.conversation_state.current_agent = self.agent_type
        
        # Get tools
        file_tools = get_file_tools(self.project_context) or []
        agent_tools = get_agent_tools() or []
        self.tools = [
            *file_tools,
            *agent_tools
        ]

        # Set up LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=0.5,
            format="json",
            verbose=verbose,
            num_predict=-2,
            num_ctx=32768,
            cache=False
        )
            
        # Create a tool map for easy lookup
        self.tool_map = {}
        for tool in self.tools:
            self.tool_map[tool.name] = tool
            
        # Update action executor with new tools
        self.action_executor = ActionExecutor(self.tool_map, self.project_context, debug=self.debug)
    
    def set_tool_callback(self, callback):
        """Set a callback function to be called before tool execution"""
        self.tool_callback = callback
        # Also set it on the action executor
        if hasattr(self, 'action_executor'):
            self.action_executor.set_tool_callback(callback)
    
    def chat(self, message: str) -> str:
        """Chat with the agent using sequential action protocol."""
        try:
            # Start a new conversation turn
            self.conversation_state.add_user_message(message)

            # Increment turn count at the beginning of each chat interaction
            self.conversation_state.turn_count += 1

            # Reset task data for each new chat
            self.conversation_state.reset_task()

            # Store the task message
            self.conversation_state.store_task_data("task", message)
            
            # Print debug info if debug mode is on
            if self.debug:
                print(f"\nDEBUG - Starting new conversation turn (Agent: {self.agent_type.value})")
                print(f"User message: {message}")
                print(f"Available tools: {len(self.tools)}")

            # Process actions in a loop until we get a terminal response
            continue_conversation = True
            final_response = "No response generated"

            while continue_conversation:
                # Ensure agent_type is synced with conversation_state before each action
                if self.agent_type != self.conversation_state.current_agent:
                    # Agent type has changed - update tools and state
                    self.agent_type = self.conversation_state.current_agent
                    
                    if self.debug:
                        print(f"\nDEBUG - Switched to {self.agent_type.value} agent, updated tools and recreated agent")
                
                # Invoke the agent to get actions
                if self.debug:
                    print(f"\nDEBUG - Invoking agent for next actions (Agent: {self.agent_type.value})")
            
                # Get the appropriate system prompt based on agent type
                if self.agent_type == AgentTypeEnum.MAIN:
                    system_prompt = get_main_agent_prompt()
                elif self.agent_type == AgentTypeEnum.SUB:
                    system_prompt = get_sub_agent_prompt()

                # Format conversation history
                conversation_history = "\n\n=== CONVERSATION HISTORY ===\n"
                for msg in self.conversation_state.message_history:
                    role = msg["role"]
                    content = msg["content"]
                    conversation_history += f"{role.upper()}: {content}\n"
                
                # For the main agent, include results from sub-agents in the conversation context
                subagent_results = ""
                if self.agent_type == AgentTypeEnum.MAIN:
                    subagent_results = "\n\n=== SUB-AGENT RESULTS ===\n"
                    result = self.conversation_state.get_task_data("sub_result")
                    if result:
                        subagent_results += f"--- SUB-AGENT RESULT ---\n{result}\n\n"
                    else:
                        subagent_results = ""
                
                # For sub-agents, include their specific prompt
                subagent_prompt = ""
                if self.agent_type == AgentTypeEnum.SUB:
                    prompt = self.conversation_state.get_task_data("subagent_prompt")
                    if prompt:
                        subagent_prompt = f"\n\n=== TASK PROMPT ===\n{prompt}\n"

                # Build file system context
                file_system_context = "\n\n=== FILE SYSTEM CONTEXT ===\n"
                file_system_context += get_file_system_prompt()
                file_system_tree = self.project_context.build_full_directory_tree(self.conversation_state)
                file_system_context += self.project_context.format_directory_tree_as_string(file_system_tree)

                # Build code context - both agents get full file contents
                code_context = "\n\n=== CODE CONTEXT ===\n"
                code_context += get_code_prompt()
                code_context += self.conversation_state.get_code_context_string()

                # Format action history without showing results
                action_history = "\n\n=== ACTION HISTORY ===\n"
                action_history += get_action_hist_prompt()
                if self.conversation_state.action_history:
                    action_list = []
                    for i, action in enumerate(self.conversation_state.action_history):
                        action_name = action.get('action', 'unknown')
                        
                        # Determine status based on action type and results
                        if action_name == "list_files" and 'result' in action:
                            # For list_files, check if there was an error or if directory doesn't exist
                            result_text = action['result']
                            if "Error:" in result_text or "does not exist" in result_text:
                                status = "FAILED"
                            else:
                                # Success if we got a valid directory listing (even if empty)
                                status = "SUCCESS"
                        else:
                            status = "SUCCESS" if "error" not in action else "FAILED"

                        # Create a simple action summary without results
                        if action_name == "read_file":
                            file_path = action.get('parameters', {}).get('file_path', 'unknown')
                            action_list.append(f"Action {i+1}: Read file '{file_path}' - {status}")
                        elif action_name == "write_file":
                            file_path = action.get('file_path', action.get('parameters', {}).get('file_path_content', 'unknown').split('|', 1)[0].strip() if '|' in action.get('parameters', {}).get('file_path_content', '') else action.get('parameters', {}).get('file_path_content', 'unknown'))
                            action_list.append(f"Action {i+1}: Wrote file '{file_path}' - {status}")
                        elif action_name == "update_file":
                            file_path = action.get('parameters', {}).get('file_path', 'unknown')
                            action_list.append(f"Action {i+1}: Updated file '{file_path}' - {status}")
                        elif action_name == "list_files":
                            dir_path = action.get('parameters', {}).get('directory', '.')
                            action_list.append(f"Action {i+1}: Listed files in '{dir_path}' - {status}")
                        elif action_name == "final_answer":
                            action_list.append(f"Action {i+1}: Ended turn - {status}")
                        elif action_name == "invoke_agent":
                            agent_type = action.get('parameters', {}).get('agent_type', 'unknown')
                            action_list.append(f"Action {i+1}: Invoked {agent_type} agent - {status}")
                        elif action_name == "respond_to_master":
                            action_list.append(f"Action {i+1}: Responded to master agent - {status}")
                        else:
                            params = action.get('parameters', {})
                            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
                            action_list.append(f"Action {i+1}: {action_name}({param_str}) - {status}")

                    action_history += "\n".join(action_list)
                else:
                    action_history += "No previous actions.\n"

                # Format latest action result
                latest_action_result = "\n\n=== PREVIOUS ACTION RESULT ===\n"
                latest_action_result += get_previous_action_prompt()
                if self.conversation_state.latest_action_result:
                    latest_action_result += self.format_action_results([self.conversation_state.latest_action_result])
                else:
                    latest_action_result += "No previous action results.\n"

                # Add to the comprehensive prompt
                if self.agent_type == AgentTypeEnum.MAIN:
                    comprehensive_prompt = (
                        f"{system_prompt}\n\n"
                        f"{file_system_context}\n\n"
                        f"{code_context}\n\n"
                        f"{action_history}\n"
                        f"{latest_action_result}\n"
                        f"{conversation_history}"
                    )
                else:
                    comprehensive_prompt = (
                        f"{system_prompt}\n\n"
                        f"{file_system_context}\n\n"
                        f"{code_context}\n\n"
                        f"{subagent_prompt}\n"
                        f"{action_history}\n"
                        f"{latest_action_result}\n"
                    )
                    
                # Add sub-agent specific components
                if subagent_results:
                    comprehensive_prompt += f"\n{subagent_results}"

                # Save the comprehensive message for debugging
                debug_file = Path(__file__).parent.parent / "last_message.txt"
                with open(debug_file, "w") as f:
                    f.write(comprehensive_prompt)

                if self.debug:
                    print(f"\nDEBUG - Input to model:\n{comprehensive_prompt[:500]}...[truncated]")

                # Run agent with the comprehensive context
                response = self.llm.invoke(comprehensive_prompt)

                agent_output = response.content

                if self.debug:
                    print(f"\nDEBUG - RAW MODEL OUTPUT:\n{agent_output}")

                # Parse the actions from the model response
                actions = self.json_parser.parse(agent_output)

                if self.debug:
                    print(f"\nDEBUG - PARSED ACTIONS ({len(actions)}):")
                    print(self.json_parser.format_for_agent(actions))

                # Check if this is a final response (only respond action or final_answer)
                is_final = self.conversation_state.is_final_response(actions)

                if is_final:
                    if self.debug:
                        print("\nDEBUG - Final response received, ending conversation turn")

                    # Execute the actions
                    action_results = self.action_executor.execute_actions(actions, self.conversation_state)
                    self.conversation_state.add_action_results(action_results)

                    # Get the final message to return (from respond or final_answer action)
                    final_message = None
                    for action in actions:
                        if action["action"] in ["final_answer"]:
                            final_message = action["parameters"].get("message", "Task completed.")
                            break

                    if final_message:
                        # Add the assistant's response to the message history
                        self.conversation_state.add_assistant_message(final_message)
                        final_response = final_message
                    else:
                        final_response = "Task completed."

                    # Mark the conversation turn as complete
                    continue_conversation = False

                # Only execute actions if this is not a final response (we already executed it above)
                elif continue_conversation:
                    # Execute the actions
                    if self.debug:
                        print("\nDEBUG - Executing action sequence")

                    # Execute all actions in sequence
                    action_results = self.action_executor.execute_actions(actions, self.conversation_state)

                    # Store the results for the next round
                    self.conversation_state.add_action_results(action_results)

                    # Check if we should continue
                    continue_conversation = self.conversation_state.should_continue_action_sequence()

                # If we're not continuing without an explicit end, get the last response message
                if not continue_conversation and not is_final:
                    # Find the last respond action
                    for result in reversed(action_results):
                        if result["action"] == "final_answer" and "message" in result:
                            final_response = result["message"]
                            break

            return final_response

        except Exception as e:
            if self.debug:
                import traceback
                print(f"\nDEBUG - ERROR IN CHAT: {str(e)}")
                print(traceback.format_exc())

            return f"An error occurred while processing your request: {str(e)}"
        
    def format_action_results(self, results):
        """Format action results more clearly for the model.

        Only formats the most recent action result.
        """
        if not results:
            return "No actions completed."

        # Get the most recent result
        result = results[-1]

        formatted = []
        action_name = result.get('action', 'unknown')
        # Determine status based on action type and results
        if action_name == "list_files" and 'result' in result:
            # For list_files, check if there was an error or if directory doesn't exist
            result_text = result['result']
            if "Error:" in result_text or "does not exist" in result_text:
                status = "FAILED"
            else:
                # Success if we got a valid directory listing (even if empty)
                status = "SUCCESS"
        else:
            status = "SUCCESS" if "error" not in result else "FAILED"

        # Format based on action type for better clarity
        if action_name == "list_files":
            formatted.append(f"✓ Latest action: Listed files in directory '{result.get('parameters', {}).get('directory', 'unknown')}' - {status}")
            if status == "SUCCESS" and 'result' in result:
                # Include a short summary of the results
                files_count = result['result'].count('📄')
                dirs_count = result['result'].count('📁')
                formatted.append(f"  Found {files_count} files and {dirs_count} directories")
                # Include a brief summary, the full structure will be in FILE SYSTEM CONTEXT
                formatted.append(f"  Check the FILE SYSTEM CONTEXT section for the complete directory structure.")
            elif status == "FAILED":
                if 'result' in result and ("Error:" in result['result'] or "does not exist" in result['result']):
                    formatted.append(f"  Error: {result['result']}")
                else:
                    formatted.append(f"  Error: {result.get('result', 'Unknown error')}")
        elif action_name == "read_file":
            file_path = result.get('parameters', {}).get('file_path', 'unknown')
            formatted.append(f"✓ Latest action: Read file '{file_path}' - {status}")
            if status == "FAILED" and 'result' in result:
                formatted.append(f"  Error: {result['result']}")
            elif status == "SUCCESS":
                # Don't include content here - it will be in CODE CONTEXT
                formatted.append(f"  Check the CODE CONTEXT section for the content of this file.")
        elif action_name == "write_file":
            file_path = result.get('file_path', result.get('parameters', {}).get('file_path_content', 'unknown').split('|', 1)[0].strip() if '|' in result.get('parameters', {}).get('file_path_content', '') else result.get('parameters', {}).get('file_path_content', 'unknown'))
            formatted.append(f"✓ Latest action: Wrote file '{file_path}' - {status}")
            if status == "FAILED" and 'result' in result:
                formatted.append(f"  Error: {result['result']}")
            elif status == "SUCCESS":
                # Don't include content here - it will be in CODE CONTEXT
                formatted.append(f"  Check the CODE CONTEXT section for the content of this file.")
        else:
            # Generic format for other actions
            formatted.append(f"✓ Latest action: Executed {action_name} - {status}")
            if status == "SUCCESS" and 'result' in result:
                formatted.append(f"  Result: {result['result']}")

        return "\n".join(formatted)

    def cleanup(self):
        """Clean up resources when the agent is no longer needed.

        This method should be called when you're done using the agent to properly
        release resources and clear the model from memory.
        """
        if self.debug:
            print("Cleaning up agent resources...")

        # Clear any cached model data
        if hasattr(self, 'llm') and hasattr(self.llm, 'client'):
            try:
                # Some langchain models have a cleanup method
                if hasattr(self.llm, 'cleanup'):
                    self.llm.cleanup()

                # For Ollama models, we can close the client if it exists
                if hasattr(self.llm, 'client') and hasattr(self.llm.client, 'close'):
                    self.llm.client.close()

                # Or if it has a session attribute that can be closed
                if hasattr(self.llm, 'client') and hasattr(self.llm.client, 'session') and hasattr(self.llm.client.session, 'close'):
                    self.llm.client.session.close()
            except Exception as e:
                if self.debug:
                    print(f"Error during model cleanup: {e}")

        # Clear conversation state
        if hasattr(self, 'conversation_state'):
            self.conversation_state = None

        # Mark as not initialized
        self._initialized = False

        if self.debug:
            print("Agent cleanup completed")

    def __del__(self):
        """Destructor to ensure cleanup happens."""
        if hasattr(self, '_initialized') and self._initialized:
            self.cleanup()