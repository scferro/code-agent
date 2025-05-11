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
from codeagent.tools.code_tools import get_code_tools
from codeagent.tools.execution_tools import get_execution_tools
from codeagent.context.project_context import ProjectContext
from codeagent.agent.prompts import (
    get_agent_prompt,
)
from codeagent.agent.json_parser import JsonResponseParser
from codeagent.agent.action_executor import ActionExecutor
from codeagent.agent.conversation_state import ConversationState

console = Console()

class CodeAgent:
    """Main agent class that orchestrates the coding assistant"""

    def __init__(self, project_dir=".", model_name="gemma3:27b", verbose=True, debug=False):
        self.project_dir = Path(project_dir).absolute()
        self.model_name = model_name
        self.verbose = verbose
        self.debug = debug
        self.tool_callback = None

        # Initialize context
        self.project_context = ProjectContext(project_dir)

        # Initialize JSON parser and state management
        self.json_parser = JsonResponseParser()
        self.conversation_state = ConversationState()

        # Set up LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=0.3,
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
            code_tools = get_code_tools(self.project_context) or []
            execution_tools = get_execution_tools(self.project_context) or []

            self.tools = [
                *file_tools,
                *code_tools,
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
        system_message = get_agent_prompt(self.project_context)
        
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

    def process_task(self, task_description):
        """Process a coding task using a multi-phase approach"""
        try:
            # Add initial system context from .agent.md files
            static_context = self.project_context.get_static_context_summary()
            if static_context:
                self.memory.chat_memory.add_message(AIMessage(content=f"Project context loaded: {static_context}"))
            
            # Phase 1: Exploration
            print("[bold]Phase 1: Exploration[/bold]")
            exploration_result = self._run_exploration_phase(task_description)
            
            # Phase 2: Planning
            print("[bold]Phase 2: Planning[/bold]")
            plan = self._run_planning_phase(task_description, exploration_result)
            
            # Phase 3: Execution with integrated verification
            print("[bold]Phase 3: Execution with Verification[/bold]")
            solution = self._run_execution_phase(task_description, plan)

            return solution
        except Exception as e:
            print(f"[bold red]Error during task processing:[/bold red] {str(e)}")
            import traceback
            print(traceback.format_exc())
            return f"An error occurred: {str(e)}"
    
    def _run_exploration_phase(self, task: str) -> str:
        """Run the exploration phase to understand the project"""
        try:
            # Run agent with exploration focus
            result = self.agent_executor.invoke({
                "input": f"EXPLORATION PHASE: I need to explore this codebase to solve this task: {task}"
            })

            # Parse output as JSON and handle accordingly
            try:
                action, params = self.json_parser.parse(result["output"])
                if action == "respond":
                    exploration_result = params.get("message", "No exploration results.")
                else:
                    exploration_result = result["output"]
            except:
                exploration_result = result["output"]

            # Add exploration summary message to memory
            self.memory.chat_memory.add_message(HumanMessage(content="Please summarize what you've learned about this codebase."))

            # Get exploration summary
            summary_result = self.agent_executor.invoke({
                "input": "Based on your exploration, summarize the key files, structure, and components relevant to my task."
            })

            # Parse output as JSON and handle accordingly
            try:
                action, params = self.json_parser.parse(summary_result["output"])
                if action == "respond":
                    return params.get("message", "No exploration summary.")
                else:
                    return summary_result["output"]
            except:
                return summary_result["output"]
        except Exception as e:
            if self.debug:
                import traceback
                print(f"Error in exploration phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during exploration: {str(e)}"
    
    def _run_planning_phase(self, task: str, exploration_result: str) -> str:
        """Run the planning phase to create a solution plan"""
        try:
            # Run agent with planning focus
            result = self.agent_executor.invoke({
                "input": f"PLANNING PHASE: Based on your exploration, create a detailed step-by-step plan to implement this task: {task}"
            })

            # Parse output as JSON and handle accordingly
            try:
                action, params = self.json_parser.parse(result["output"])
                if action == "respond":
                    return params.get("message", "No planning results.")
                else:
                    return result["output"]
            except:
                return result["output"]
        except Exception as e:
            if self.debug:
                import traceback
                print(f"Error in planning phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during planning: {str(e)}"
    
    def _run_execution_phase(self, task: str, plan: str) -> str:
        """Run the execution phase with integrated verification to implement the solution"""
        try:
            # Run agent with execution focus that includes verification
            result = self.agent_executor.invoke({
                "input": f"EXECUTION PHASE: Implement and verify the solution for this task according to the plan we created: {task}"
            })

            # Parse output as JSON and handle accordingly
            try:
                action, params = self.json_parser.parse(result["output"])
                if action == "respond":
                    return params.get("message", "No execution results.")
                else:
                    return result["output"]
            except:
                return result["output"]
        except Exception as e:
            if self.debug:
                import traceback
                print(f"Error in execution phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during execution: {str(e)}"

    # The verification phase is now integrated into the execution phase
    
    def chat(self, message: str) -> str:
        """Chat with the agent using sequential action protocol."""
        try:
            # Start a new conversation turn
            self.conversation_state.add_user_message(message)

            # Increment turn count at the beginning of each chat interaction
            self.conversation_state.turn_count += 1

            # Always start fresh for each chat in planning phase
            self.conversation_state.reset_task()
            # Store the task message
            self.conversation_state.store_task_data("task", message)
            print(f"Starting new task in planning phase: {message[:50]}...")

            # Print debug info if debug mode is on
            if self.debug:
                print("\nDEBUG - Starting new conversation turn")
                print(f"User message: {message}")
                print(f"Available tools: {len(self.tools)}")
                print(f"Current execution phase: {self.conversation_state.execution_phase}")

            # Process actions in a loop until we get a terminal response
            continue_conversation = True
            final_response = "No response generated"

            # Get the system prompt
            system_prompt = get_agent_prompt(self.project_context)

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

                # Format action history with clear SUCCESS/FAILURE indicators
                action_history = "\n\n=== PREVIOUS ACTIONS COMPLETED ===\n"
                if self.conversation_state.action_history:
                    action_history += self.format_action_results(self.conversation_state.action_history)
                else:
                    action_history += "No previous actions.\n"

                # Format current actions results with clear SUCCESS/FAILURE indicators
                current_results = "\n\n=== MOST RECENT ACTION RESULTS ===\n"
                if self.conversation_state.current_action_results:
                    current_results += self.format_action_results(self.conversation_state.current_action_results)
                else:
                    current_results += "No current action results.\n"

                # Add phase information if in a specific phase
                phase_instructions = ""

                # Always get the latest phase from the state
                phase = self.conversation_state.execution_phase.upper()
                print(f"DEBUG - Preparing prompt for phase: {phase}")

                phase_instructions = f"\n\n=== CURRENT EXECUTION PHASE: {phase} ===\n"

                # Add phase-specific instructions
                if phase == "PLANNING":
                    plan_task = self.conversation_state.get_task_data("task", message)
                    from codeagent.agent.workflows import format_planning_prompt, format_planning_examples
                    phase_instructions += format_planning_prompt(plan_task)
                    # phase_instructions += format_planning_examples()
                    print(f"DEBUG - Added planning prompt for task: {plan_task}")

                elif phase == "EXECUTION":
                    plan = self.conversation_state.get_task_data("plan", {})
                    from codeagent.agent.workflows import format_execution_prompt
                    phase_instructions += format_execution_prompt(plan)
                    print(f"DEBUG - Added execution prompt with plan: {plan}")

                # We no longer have a separate verification phase

                # Print verbose info about the current phase
                print(f"Current execution phase: {phase}")
                if phase == "PLANNING":
                    print("Waiting for the model to complete planning...")
                elif phase == "EXECUTION":
                    print("Waiting for the model to complete execution with verification...")
                elif phase == "DONE":
                    print("Task has been completed.")

                # Debug info about phase instructions
                if self.debug and self.conversation_state.execution_phase != "none":
                    print(f"\nDEBUG - Building prompt with phase: {self.conversation_state.execution_phase}")
                    print(f"Phase instructions length: {len(phase_instructions)} characters")

                # Add to the comprehensive prompt
                comprehensive_prompt = (
                    f"{system_prompt}\n\n"
                    f"{phase_instructions}\n"
                    f"{action_history}\n"
                    f"{current_results}\n"
                    f"{conversation_history}"
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

                # Check if this is a final response (only respond action)
                is_final = self.conversation_state.is_final_response(actions)

                if is_final:
                    if self.debug:
                        print("\nDEBUG - Final response received, ending conversation turn")

                    # Get the response message
                    final_response = actions[0]["parameters"].get("message", "No response provided")

                    # Show the response without the tool summary prefix
                    if self.debug:
                        print(f"\nDEBUG - FINAL RESPONSE: {final_response}")

                    # Execute the action to display the message to the user and add it to history
                    action_results = self.action_executor.execute_actions(actions, self.conversation_state)
                    self.conversation_state.add_action_results(action_results)

                    # Add the assistant's response to the message history explicitly
                    self.conversation_state.add_assistant_message(final_response)

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

                # If we're not continuing, get the last response message
                if not continue_conversation:
                    # Find the last respond action
                    for result in reversed(action_results):
                        if result["action"] == "respond":
                            final_response = result.get("result", "Action completed")
                            break

            return final_response

        except Exception as e:
            if self.debug:
                import traceback
                print(f"\nDEBUG - ERROR IN CHAT: {str(e)}")
                print(traceback.format_exc())

            return f"An error occurred while processing your request: {str(e)}"
        
    def format_action_results(self, results):
        """Format action results more clearly for the model"""
        formatted = []
        for i, result in enumerate(results):
            action_name = result.get('action', 'unknown')
            status = "SUCCESS" if "error" not in result else "FAILED"

            # Format based on action type for better clarity
            if action_name == "list_files":
                formatted.append(f"✓ ACTION {i+1}: Listed files in directory '{result.get('parameters', {}).get('directory', 'unknown')}' - {status}")
                if status == "SUCCESS" and 'result' in result:
                    # Include a short summary of the results
                    files_count = result['result'].count('📄')
                    dirs_count = result['result'].count('📁')
                    formatted.append(f"  Found {files_count} files and {dirs_count} directories")
                    # Include the full file listing result for the model to use
                    formatted.append("\nFILE STRUCTURE:\n" + result['result'])
            elif action_name == "read_file":
                file_path = result.get('parameters', {}).get('file_path', 'unknown')
                formatted.append(f"✓ ACTION {i+1}: Read file '{file_path}' - {status}")
                if status == "FAILED" and 'result' in result:
                    formatted.append(f"  Error: {result['result']}")
                elif status == "SUCCESS" and 'result' in result:
                    # Include the file content for the model to use
                    formatted.append("\nFILE CONTENT:\n" + result['result'])
            elif action_name == "search_code":
                formatted.append(f"✓ ACTION {i+1}: Searched for '{result.get('parameters', {}).get('query', 'unknown')}' - {status}")
                if status == "SUCCESS" and 'result' in result:
                    # Include the search results for the model to use
                    formatted.append("\nSEARCH RESULTS:\n" + result['result'])
            else:
                # Generic format for other actions
                formatted.append(f"✓ ACTION {i+1}: Executed {action_name} - {status}")

        return "\n".join(formatted)