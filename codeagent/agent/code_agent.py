"""Main agent class that orchestrates the coding assistant"""
import os
from pathlib import Path
import time
from typing import List, Dict, Any, Optional

from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain.agents import initialize_agent, AgentType
from langchain.schema import HumanMessage, AIMessage

from rich.console import Console

from codeagent.tools.file_tools import get_file_tools
from codeagent.tools.execution_tools import get_execution_tools
from codeagent.agent.project_context import ProjectContext
from codeagent.agent.prompts import (
    get_agent_prompt,
    get_code_prompt,
    get_action_hist_prompt,
    get_file_system_prompt,
    get_previous_action_prompt
)
from codeagent.agent.json_parser import JsonResponseParser
from codeagent.agent.action_executor import ActionExecutor
from codeagent.agent.conversation_state import ConversationState

console = Console()

class CodeAgent:
    """Main agent class that orchestrates the coding assistant"""

    def __init__(self, project_dir=".", model_name="gemma3:12b", verbose=True, debug=False):
        self.project_dir = Path(project_dir).absolute()
        self.model_name = model_name
        self.verbose = verbose
        self.debug = debug
        self.tool_callback = None
        self._initialized = True

        # Initialize context
        self.project_context = ProjectContext(project_dir)

        # Initialize JSON parser and state management
        self.json_parser = JsonResponseParser()
        self.conversation_state = ConversationState()

        # Set up LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=0.5,
            format="json",
            verbose=verbose,
            num_predict=-2,
            cache=False,
            num_ctx=32768
        )

        # Set up memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Initialize tools
        try:
            file_tools = get_file_tools(self.project_context) or []
            execution_tools = get_execution_tools(self.project_context) or []

            self.tools = [
                *file_tools,
                *execution_tools
            ]

            # Create a tool map for easy lookup
            self.tool_map = {}
            for tool in self.tools:
                self.tool_map[tool.name] = tool

            # Initialize action executor
            self.action_executor = ActionExecutor(self.tool_map, self.project_context, debug=debug)

            if not self.tools:
                print("Warning: No tools were loaded. Check your tool implementation files.")
                # Provide at least an empty list
                self.tools = []
        except Exception as e:
            print(f"Error loading tools: {e}")
            import traceback
            print(traceback.format_exc())
            # Ensure we have at least an empty list
            self.tools = []

        # Debug tools before creating agent
        if self.debug:
            print("\n=========== TOOLS IN AGENT INIT ===========")
            print(f"Total tools: {len(self.tools)}")
            for i, t in enumerate(self.tools):
                print(f"Tool {i}: {getattr(t, 'name', str(t))}")
                print(f"Type: {type(t)}")
                print(f"Has run: {hasattr(t, 'run')}")
                print(f"Has invoke: {hasattr(t, 'invoke')}")
                print(f"Has stop: {hasattr(t, 'stop')}")
                print("---")
            print("===========================================\n")

        # Create agent
        self._create_agent()
    
    def _create_agent(self):
        """Create the LangChain agent with the specified tools"""
        # Use the structured chat agent
        from langchain.agents import AgentType, initialize_agent
        
        # Get the system prompt from prompts.py
        system_message = get_agent_prompt()
        
        # Initialize a structured chat agent with the ZERO_SHOT_REACT_DESCRIPTION agent
        from langchain.chains.conversation.memory import ConversationBufferWindowMemory
        
        # Create a window memory to limit context size
        window_memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=5  # Remember last 5 exchanges
        )
        
        # Debug before agent initialization
        if self.debug:
            print("\n=========== AGENT INITIALIZATION ===========")
            print(f"Agent type: {AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION}")
            print(f"LLM type: {type(self.llm)}")
            print(f"Memory type: {type(window_memory)}")
            print(f"Number of tools: {len(self.tools)}")
            print("===========================================\n")

        try:
            # Try a different agent type
            self.agent_executor = initialize_agent(
                self.tools,
                self.llm,
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=self.verbose,
                memory=window_memory,
                agent_kwargs={"system_message": system_message},
                handle_parsing_errors=True,
                max_iterations=30
            )

            if self.debug:
                print("\n=========== AGENT CREATED SUCCESSFULLY ===========")
                print(f"Agent type: {type(self.agent_executor)}")
                print(f"Agent dir: {dir(self.agent_executor)[:10]}...")
                print("=================================================\n")

        except Exception as e:
            if self.debug:
                print(f"\n=========== AGENT CREATION FAILED ===========")
                print(f"Error: {str(e)}")
                import traceback
                print(traceback.format_exc())
                print("==============================================\n")
            raise
    
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
            print(f"Starting new task: {message[:50]}...")

            # Print debug info if debug mode is on
            if self.debug:
                print("\nDEBUG - Starting new conversation turn")
                print(f"User message: {message}")
                print(f"Available tools: {len(self.tools)}")

            # Process actions in a loop until we get a terminal response
            continue_conversation = True
            final_response = "No response generated"

            # Get the system prompt
            system_prompt = get_agent_prompt()

            while continue_conversation:
                # Invoke the agent to get actions
                if self.debug:
                    print("\nDEBUG - Invoking agent for next actions")

                # Format conversation history
                conversation_history = "\n\n=== CONVERSATION HISTORY ===\n"
                for msg in self.conversation_state.message_history:
                    role = msg["role"]
                    content = msg["content"]
                    conversation_history += f"{role.upper()}: {content}\n"

                # Add assistant responses from action history to conversation history
                assistant_responses = []
                for action in self.conversation_state.action_history:
                    if action["action"] == "respond" and "original_parameters" in action:
                        if "message" in action["original_parameters"]:
                            assistant_message = action["original_parameters"]["message"]
                            if assistant_message not in assistant_responses:
                                conversation_history += f"ASSISTANT: {assistant_message}\n"
                                assistant_responses.append(assistant_message)

                # Build file system context
                file_system_context = "\n\n=== FILE SYSTEM CONTEXT ===\n"
                file_system_context += get_file_system_prompt()
                file_system_tree = self.project_context.build_full_directory_tree(self.conversation_state)
                file_system_context += self.project_context.format_directory_tree_as_string(file_system_tree)

                # Build code context
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
                        status = "SUCCESS" if "error" not in action else "FAILED"

                        # Create a simple action summary without results
                        if action_name == "read_file":
                            file_path = action.get('parameters', {}).get('file_path', 'unknown')
                            action_list.append(f"Action {i+1}: Read file '{file_path}' - {status}")
                        elif action_name == "write_file":
                            file_path = action.get('file_path', action.get('parameters', {}).get('file_path_content', 'unknown').split('|', 1)[0].strip() if '|' in action.get('parameters', {}).get('file_path_content', '') else action.get('parameters', {}).get('file_path_content', 'unknown'))
                            action_list.append(f"Action {i+1}: Wrote file '{file_path}' - {status}")
                        elif action_name == "list_files":
                            dir_path = action.get('parameters', {}).get('directory', '.')
                            action_list.append(f"Action {i+1}: Listed files in '{dir_path}' - {status}")
                        elif action_name == "search_code":
                            query = action.get('parameters', {}).get('query', 'unknown')
                            action_list.append(f"Action {i+1}: Searched for '{query}' - {status}")
                        elif action_name == "respond":
                            action_list.append(f"Action {i+1}: Responded to user - {status}")
                        elif action_name == "end_turn":
                            action_list.append(f"Action {i+1}: Ended turn - {status}")
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

                # Task-specific context
                last_message = f"\n\n=== LAST MESSAGE FROM USER ===\n{message}\n"

                # Add to the comprehensive prompt
                comprehensive_prompt = (
                    f"{system_prompt}\n\n"
                    f"{file_system_context}\n\n"
                    f"{code_context}\n\n"
                    f"{action_history}\n"
                    f"{latest_action_result}\n"
                    f"{conversation_history}"
                    # f"{last_message}\n"
                )

                # Save the comprehensive message for debugging
                with open("last_message.txt", "w") as f:
                    f.write(comprehensive_prompt)

                if self.debug:
                    print(f"\nDEBUG - Input to model:\n{comprehensive_prompt[:500]}...[truncated]")

                # Run agent with the comprehensive context
                response = self.agent_executor.invoke({
                    "input": comprehensive_prompt
                })

                agent_output = response["output"]

                if self.debug:
                    print(f"\nDEBUG - RAW MODEL OUTPUT:\n{agent_output}")

                # Parse the actions from the model response
                actions = self.json_parser.parse(agent_output)

                if self.debug:
                    print(f"\nDEBUG - PARSED ACTIONS ({len(actions)}):")
                    print(self.json_parser.format_for_agent(actions))

                # Check if this is a final response (only respond action or end_turn)
                is_final = self.conversation_state.is_final_response(actions)

                if is_final:
                    if self.debug:
                        print("\nDEBUG - Final response received, ending conversation turn")

                    # Execute the actions
                    action_results = self.action_executor.execute_actions(actions, self.conversation_state)
                    self.conversation_state.add_action_results(action_results)

                    # Get the final message to return (from respond or end_turn action)
                    final_message = None
                    for action in actions:
                        if action["action"] in ["respond", "end_turn"]:
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
                        if result["action"] == "respond" and "message" in result:
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
        elif action_name == "search_code":
            formatted.append(f"✓ Latest action: Searched for '{result.get('parameters', {}).get('query', 'unknown')}' - {status}")
            if status == "SUCCESS" and 'result' in result:
                # Include the search results for the model to use
                formatted.append("\nSEARCH RESULTS:\n" + result['result'])
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

        # Clear memory
        if hasattr(self, 'memory'):
            self.memory.clear()

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