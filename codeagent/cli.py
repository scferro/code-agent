"""Command line interface for CodeAgent"""
import click
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from codeagent.agent.code_agent import CodeAgent
from codeagent.tools.permissions import request_permission, set_status_context

console = Console()

@click.group()
@click.version_option()
def cli_app():
    """CodeAgent - An AI coding assistant powered by Ollama"""
    pass

@cli_app.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False), default=".")
def init(project_dir):
    """Initialize a new project for CodeAgent"""
    project_path = Path(project_dir).absolute()
    console.print(f"Initializing project in [bold]{project_path}[/bold]")
    
    # Check if .agent.md already exists
    agent_md_path = project_path / ".agent.md"
    
    if agent_md_path.exists():
        console.print("[yellow]A .agent.md file already exists in this project.[/yellow]")
        overwrite = click.confirm("Do you want to overwrite it?", default=False)
        if not overwrite:
            console.print("Initialization aborted.")
            return
    
    # Create .agent.md file with template
    template = """# Project Configuration for CodeAgent

## Project Description
Brief description of what this project does.

## Architecture
Overview of the project's architecture and main components.

## Code Style
Coding conventions and style guidelines for this project.

## Common Commands
Commands frequently used in this project:

- Build: `command to build the project`
- Test: `command to run tests`
- Run: `command to run the project`

## File Descriptions
Key files and directories in this project:

- `src/`: Source code directory
- `tests/`: Test directory
- `README.md`: Project documentation

## Custom Tools
Custom tools or scripts specific to this project:

- `scripts/build.sh`: Build script
"""
    
    with open(agent_md_path, "w") as f:
        f.write(template)
    
    # Create .agent.local.md for user-specific settings
    agent_local_md_path = project_path / ".agent.local.md"
    
    if not agent_local_md_path.exists():
        with open(agent_local_md_path, "w") as f:
            f.write("""# Local Configuration for CodeAgent
# This file is for your personal settings and is not checked into version control.

## Personal Preferences
Your personal preferences for this project.

## Environment Setup
Your specific environment settings.
""")
    
    # Add .agent.local.md to .gitignore if .gitignore exists
    gitignore_path = project_path / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            content = f.read()
        
        if ".agent.local.md" not in content:
            with open(gitignore_path, "a") as f:
                f.write("\n# CodeAgent local settings\n.agent.local.md\n")
    
    console.print(Panel(
        "[bold green]✓[/bold green] Project initialized successfully!\n\n"
        "Created:\n"
        f"- [bold]{agent_md_path}[/bold] - Project-level agent configuration\n"
        f"- [bold]{agent_local_md_path}[/bold] - Your personal settings (gitignored)\n\n"
        "Edit these files to customize CodeAgent for your project.",
        title="CodeAgent Initialization",
        expand=False
    ))

@cli_app.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--model", "-m", help="Ollama model to use", default="devstral")
@click.option("--verbose/--quiet", "-v/-q", default=False, help="Show detailed processing logs")
@click.option("--debug", is_flag=True, default=False, help="Enable debug output")
def chat(project_dir, model, verbose, debug):
    """Start an interactive chat session"""
    project_path = Path(project_dir).absolute()
    console.print(f"Starting chat session in [bold]{project_path}[/bold]")

    # Initialize agent as MAIN agent by default
    console.print("[bold yellow]Initializing agent...[/bold yellow]")
    from codeagent.agent.conversation_state import AgentType
    agent = CodeAgent(project_dir, model_name=model, verbose=verbose, debug=debug, agent_type=AgentType.MAIN)

    try:
        # Start chat loop
        console.print("[bold green]Chat session started. Type 'exit' to quit.[/bold green]")

        while True:
            user_input = input("\n[You]: ")

            if user_input.lower() in ("exit", "quit", "bye"):
                break

            # Note: The action execution prints the responses directly
            with console.status("[bold yellow]Processing...[/bold yellow]") as status:
                # Set the status context so permission requests can pause it
                set_status_context(status)
                agent.chat(user_input)
                # Clear the status context when done
                set_status_context(None)

            # Line break for next user input
            console.print("")
    finally:
        # Ensure cleanup happens when chat session ends
        console.print("[bold yellow]Cleaning up resources...[/bold yellow]")
        agent.cleanup()

@cli_app.command()
@click.option("--global", "scope", flag_value="global", help="Show global agent configuration")
@click.option("--local", "scope", flag_value="local", help="Show local agent configuration")
@click.option("--project", "scope", flag_value="project", default=True, help="Show project agent configuration")
@click.option("--project-dir", "-p", type=click.Path(exists=True, file_okay=False), default=".")
def config(scope, project_dir):
    """View or edit agent configuration"""
    if scope == "global":
        path = Path.home() / ".agent.md"
        title = "Global Agent Configuration"
    elif scope == "local":
        path = Path(project_dir) / ".agent.local.md"
        title = "Local Agent Configuration"
    else:  # project
        path = Path(project_dir) / ".agent.md"
        title = "Project Agent Configuration"
    
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] {path} does not exist.")
        return
    
    content = path.read_text()
    console.print(Panel(Markdown(content), title=title, expand=False))
    
    edit = click.confirm("Would you like to edit this file?", default=False)
    if edit:
        editor = os.environ.get("EDITOR", "nano")
        if request_permission("execute", f"Run editor command: {editor} {path}", "This will execute a shell command to open your editor."):
            os.system(f"{editor} {path}")
            console.print(f"[bold green]✓[/bold green] {path} has been updated.")
        else:
            console.print("[bold red]Permission denied.[/bold red] File editing cancelled.")

if __name__ == "__main__":
    cli_app()