#!/usr/bin/env python3
"""
Main entry point for the CodeAgent CLI.
"""
import sys
import click
from pathlib import Path
from rich.console import Console

from codeagent.cli import cli_app

console = Console()

def main():
    """Main entry point for the application"""
    try:        
        # Run CLI
        cli_app()
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()