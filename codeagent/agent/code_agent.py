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
    get_exploration_prompt,
    get_planning_prompt,
    get_execution_prompt,
    get_verification_prompt
)
from codeagent.agent.json_parser import JsonResponseParser

console = Console()

class CodeAgent:
    """Main agent class that orchestrates the coding assistant"""
    
    def __init__(self, project_dir=".", model_name="gemma3:12b", verbose=True):
        self.project_dir = Path(project_dir).absolute()
        self.model_name = model_name
        self.verbose = verbose
        self.tool_callback = None

        # Initialize context
        self.project_context = ProjectContext(project_dir)

        # Initialize JSON parser
        self.json_parser = JsonResponseParser()

        # Set up LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=0.5,
            format="json",
            verbose=verbose
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

            print("\n=========== AGENT CREATED SUCCESSFULLY ===========")
            print(f"Agent type: {type(self.agent_executor)}")
            print(f"Agent dir: {dir(self.agent_executor)[:10]}...")
            print("=================================================\n")

        except Exception as e:
            print(f"\n=========== AGENT CREATION FAILED ===========")
            print(f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            print("==============================================\n")
            raise
    
    def set_tool_callback(self, callback):
        """Set a callback function to be called before tool execution"""
        self.tool_callback = callback

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
            
            # Phase 3: Execution
            print("[bold]Phase 3: Execution[/bold]")
            solution = self._run_execution_phase(task_description, plan)
            
            # Phase 4: Verification
            print("[bold]Phase 4: Verification[/bold]")
            verified_solution = self._run_verification_phase(solution)
            
            return verified_solution
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
            if self.verbose:
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
            if self.verbose:
                import traceback
                print(f"Error in planning phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during planning: {str(e)}"
    
    def _run_execution_phase(self, task: str, plan: str) -> str:
        """Run the execution phase to implement the solution"""
        try:
            # Run agent with execution focus
            result = self.agent_executor.invoke({
                "input": f"EXECUTION PHASE: Implement the solution for this task according to the plan we created: {task}"
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
            if self.verbose:
                import traceback
                print(f"Error in execution phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during execution: {str(e)}"

    def _run_verification_phase(self, solution: str) -> str:
        """Run the verification phase to check the solution"""
        try:
            # Run agent with verification focus
            result = self.agent_executor.invoke({
                "input": "VERIFICATION PHASE: Please review the solution we've created. Identify any issues, edge cases, or improvements."
            })

            # Parse verification output
            try:
                action, params = self.json_parser.parse(result["output"])
                verification_result = params.get("message", result["output"]) if action == "respond" else result["output"]
            except:
                verification_result = result["output"]

            # Add final comprehensive solution message
            self.memory.chat_memory.add_message(HumanMessage(content="Now, provide the final complete solution with any improvements."))

            # Get final solution
            final_result = self.agent_executor.invoke({
                "input": "Please provide the complete final solution incorporating any improvements from the verification phase."
            })

            # Parse final output
            try:
                action, params = self.json_parser.parse(final_result["output"])
                if action == "respond":
                    return params.get("message", "No final solution provided.")
                else:
                    return final_result["output"]
            except:
                return final_result["output"]
        except Exception as e:
            if self.verbose:
                import traceback
                print(f"Error in verification phase: {str(e)}")
                print(traceback.format_exc())
            return f"Error during verification: {str(e)}"
    
    def chat(self, message: str) -> str:
        """Chat with the agent"""
        try:
            # First, check if we need to run the agent or we can parse JSON directly
            try:
                # Print debug info about our tools if verbose
                if self.verbose:
                    print("\nDEBUG - AVAILABLE TOOLS:")
                    for i, tool in enumerate(self.tools):
                        print(f"Tool {i}: {tool.name} - Type: {type(tool)}")
                        if hasattr(tool, 'func'):
                            print(f"  - Has func attribute: {tool.func.__name__}")
                        print(f"  - Methods: {[m for m in dir(tool) if not m.startswith('_')]}")

                # Run agent with user message to get JSON response
                if self.verbose:
                    print("\nDEBUG - RUNNING AGENT WITH USER MESSAGE:")
                    print(f"User message: {message}")

                response = self.agent_executor.invoke({
                    "input": message
                })
                agent_output = response["output"]

                if self.verbose:
                    print(f"\nDEBUG - AGENT OUTPUT: {agent_output}")

                # Parse the JSON response
                print("\n=========== DIRECT DEBUG OUTPUT ===========")
                print("RAW MODEL OUTPUT:", agent_output)

                action, params = self.json_parser.parse(agent_output)

                print("DIRECT DEBUG ACTION:", action)
                print("DIRECT DEBUG PARAMS:", params)
                print("==========================================\n")

                if self.verbose:
                    formatted_action = self.json_parser.format_for_agent(action, params)
                    print(f"Executing action: {formatted_action}")

                # Check if we should use the respond tool directly
                if action == "respond":
                    return params.get("message", "No response message provided.")

                # Execute the tool
                if action not in self.tool_map:
                    return f"Error: Unknown action '{action}'. Please use a valid tool."

                # Notify callback if registered
                if self.tool_callback and callable(self.tool_callback):
                    self.tool_callback(action, params)

                # Get the tool and print debug info
                tool = self.tool_map[action]

                print("\n=========== DIRECT TOOL DEBUG ===========")
                print(f"ACTION: {action}")
                print(f"TOOL TYPE: {type(tool)}")
                print(f"TOOL DIR: {dir(tool)}")
                print(f"TOOL CALLABLE: {callable(tool)}")

                # Check if this is a function or Tool object
                if hasattr(tool, 'func'):
                    print(f"TOOL HAS FUNC: {tool.func}")
                    print(f"TOOL FUNC TYPE: {type(tool.func)}")

                # Check for run/invoke methods
                if hasattr(tool, 'run'):
                    print(f"TOOL HAS RUN METHOD: {tool.run}")
                if hasattr(tool, 'invoke'):
                    print(f"TOOL HAS INVOKE METHOD: {tool.invoke}")

                print("==========================================\n")

                # Special case for respond tool - it just needs the message
                if action == "respond" and "message" in params:
                    return params["message"]

                # Special case for write_file
                if action == "write_file" and "file_path_content" in params:
                    # Format is now file_path_content with a pipe separator
                    try:
                        # Debug info
                        if self.verbose:
                            print(f"DEBUG - write_file tool type: {type(tool)}")
                            print(f"DEBUG - write_file tool dir: {dir(tool)}")
                            print(f"DEBUG - write_file param: {params['file_path_content']}")

                        # Try to extract the file path and content for direct file creation
                        file_path_content = params["file_path_content"]
                        if '|' in file_path_content:
                            parts = file_path_content.split('|', 1)
                            file_path = parts[0].strip()
                            content = parts[1] if len(parts) > 1 else ""

                            # Create the file directly
                            full_path = self.project_context.project_dir / file_path
                            full_path.parent.mkdir(parents=True, exist_ok=True)
                            full_path.write_text(content)
                            return f"Successfully wrote to {file_path}"
                        else:
                            # Try using the tool with the parameter
                            result = tool.run(params["file_path_content"])
                            return result
                    except Exception as e:
                        if self.verbose:
                            import traceback
                            print(f"DEBUG - write_file exception: {str(e)}")
                            print(traceback.format_exc())
                        return f"Error writing file: {str(e)}"

                # For other tools, try different invocation approaches with detailed debugging
                try:
                    print("\n=========== TOOL EXECUTION ATTEMPT ===========")

                    # Method 1: Try using invoke with params dict
                    try:
                        print("ATTEMPT 1: Using tool.invoke(params)")
                        if hasattr(tool, 'invoke'):
                            result = tool.invoke(params)
                            print("INVOKE SUCCESS!")
                            print("==========================================\n")
                            return result
                        else:
                            print("Tool has no invoke method, trying run...")
                    except Exception as e1:
                        print(f"INVOKE ERROR: {str(e1)}")

                    # Method 2: Try using run with the primary parameter value
                    try:
                        if len(params) == 1:
                            param_name = next(iter(params.keys()))
                            param_value = params[param_name]
                            print(f"ATTEMPT 2: Using tool.run with single param: {param_value}")
                            result = tool.run(param_value)
                            print("RUN SUCCESS!")
                            print("==========================================\n")
                            return result
                        else:
                            print("Multiple params, trying JSON...")
                    except Exception as e2:
                        print(f"RUN ERROR with single param: {str(e2)}")

                    # Method 3: Try using run with JSON string
                    try:
                        import json
                        tool_input = json.dumps(params)
                        print(f"ATTEMPT 3: Using tool.run with JSON string: {tool_input}")
                        result = tool.run(tool_input)
                        print("RUN SUCCESS with JSON!")
                        print("==========================================\n")
                        return result
                    except Exception as e3:
                        print(f"RUN ERROR with JSON: {str(e3)}")

                    # Method 4: Try direct call as function
                    try:
                        print("ATTEMPT 4: Trying direct function call")
                        if len(params) == 1:
                            param_name = next(iter(params.keys()))
                            param_value = params[param_name]
                            result = tool(param_value)
                        else:
                            result = tool(**params)
                        print("DIRECT CALL SUCCESS!")
                        print("==========================================\n")
                        return result
                    except Exception as e4:
                        print(f"DIRECT CALL ERROR: {str(e4)}")

                    print("All invocation attempts failed!")
                    print("==========================================\n")
                    return f"Error: Failed to execute {action} tool after multiple attempts"

                except Exception as e:
                    print(f"OVERALL ERROR: {str(e)}")
                    print("==========================================\n")
                    return f"Error executing tool {action}: {str(e)}"

                return result

            except Exception as e:
                if self.verbose:
                    import traceback
                    print(f"Error parsing JSON: {str(e)}")
                    print(traceback.format_exc())

                # If JSON parsing failed, treat the entire response as a message
                return f"Error processing response: {str(e)}"

        except Exception as e:
            if self.verbose:
                import traceback
                print(f"Error in chat: {str(e)}")
                print(traceback.format_exc())
            return f"An error occurred: {str(e)}"