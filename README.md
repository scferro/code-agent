# Code Agent

A Python-based intelligent coding assistant powered by LLMs through Ollama. Code Agent can understand your codebase, answer questions, and help you implement new features using a sophisticated agent system.

## Features

- Interactive chat interface with LLM-powered coding assistance
- Dual-agent architecture (main + sub-agent) for complex task decomposition
- Codebase exploration and understanding
- File creation, reading, and modification
- Project context management with .agent.md configuration
- Permission-based file operations for security
- Local execution with Ollama (no cloud API required)
- Conversation state management across multiple turns

## Installation

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/code-agent.git
   cd code-agent
   ```

2. Create a virtual environment and activate it (optional):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Configuration

### Model Configuration

By default, Code Agent uses `devstral` from Ollama. You can specify a different Ollama model using the `--model` flag:

```bash
codeagent chat --model "codellama:7b"
```

### Project Context

You can create a `.agent.md` file in your project root to provide context about your project. This will help the agent better understand your codebase:

```bash
codeagent init
```

Then edit the generated `.agent.md` file with your project specifics.

## Usage

### Interactive Chat

Start an interactive chat session in your project directory:

```bash
codeagent chat
```

You can customize the chat session with these options:

```bash
# Use a specific model
codeagent chat --model "codellama:7b"

# Use a different project directory
codeagent chat --project-dir /path/to/project

# Enable verbose output
codeagent chat --verbose

# Enable debug mode for detailed logging
codeagent chat --debug
```

### Available Commands

- `codeagent init [PROJECT_DIR]` - Initialize a project with .agent.md configuration
- `codeagent chat [OPTIONS]` - Start an interactive chat session
- `codeagent config [OPTIONS]` - View or edit agent configuration

### Examples

#### Example 1: Project Exploration

```
[You]: What files are in this project and what do they do?

[Agent]: The project contains several Python modules organized as follows:

- `codeagent/`: Main package directory
  - `agent/`: Core agent implementation
    - `code_agent.py`: Main agent class with dual-agent system
    - `conversation_state.py`: Conversation state management
    - `action_executor.py`: Action execution and tool coordination
    - `json_parser.py`: JSON response parsing from LLM
    - `project_context.py`: Project context and file tracking
    - `prompts.py`: System prompts for different agent types
  - `tools/`: Tool implementations
    - `file_tools.py`: File operations (read, write, list, update)
    - `agent_tools.py`: Agent coordination tools (invoke_agent, respond_to_master)
    - `permissions.py`: Permission management for secure operations
  - `cli.py`: Command-line interface
- `main.py`: Entry point for the application
```

#### Example 2: Code Creation

```
[You]: Create a simple Python utility to find duplicate files in a directory

[Agent]: Here's a utility that finds duplicate files based on content:

```python
# File: find_duplicates.py
import os
import hashlib
from collections import defaultdict

def get_file_hash(filepath):
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

def find_duplicates(directory):
    """Find duplicate files in a directory."""
    hashes = defaultdict(list)
    
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                file_hash = get_file_hash(filepath)
                hashes[file_hash].append(filepath)
            except Exception as e:
                print(f"Error hashing {filepath}: {e}")
    
    # Return only files with duplicates
    return {hash_val: paths for hash_val, paths in hashes.items() if len(paths) > 1}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python find_duplicates.py <directory>")
        sys.exit(1)
    
    directory = sys.argv[1]
    duplicates = find_duplicates(directory)
    
    if not duplicates:
        print("No duplicate files found.")
    else:
        print(f"Found {len(duplicates)} sets of duplicate files:")
        for i, (hash_val, paths) in enumerate(duplicates.items(), 1):
            print(f"\nDuplicate set #{i}:")
            for path in paths:
                print(f"  - {path}")
```

## Agent Architecture

Code Agent uses a sophisticated dual-agent system:

### Main Agent
- **Role**: Handles user interaction, task decomposition, and coordination
- **Capabilities**: Can delegate complex tasks to sub-agents, integrate results, provide comprehensive responses
- **Tools**: All file operations, agent coordination, user communication

### Sub-Agent
- **Role**: Focuses on specific, well-defined tasks
- **Capabilities**: Clean conversation context, access to all project files, specialized task execution
- **Tools**: File operations only (no recursion - cannot create more sub-agents)

### How It Works
1. User asks a question or requests a task
2. Main agent analyzes the complexity
3. For simple tasks: Main agent handles directly
4. For complex tasks: Main agent delegates focused sub-tasks to sub-agents
5. Sub-agents complete their tasks and return results
6. Main agent integrates results and responds to user

This architecture allows for better focus on complex multi-step problems while maintaining conversation context.

## Advanced Usage

### Using Project Context

For better assistance, create a project context file with:

```bash
codeagent init
```

Edit the generated `.agent.md` file to include:
- Project description
- Architecture overview
- Code style guidelines
- Common commands
- Key file descriptions

### Permission System

Code Agent includes a security-focused permission system:
- **Session permissions**: Valid for current session only
- **Project permissions**: Saved in `.codeagent/permissions.json` (7 days)
- **Global permissions**: Saved in `~/.codeagent/permissions.json` (30 days)

You'll be prompted to grant permissions for file operations and can choose the appropriate scope.

### Verbose and Debug Modes

Enable verbose mode for additional information about the model output:

```bash
codeagent chat --verbose
```

Enable debug mode even more information about the model output and agent status:

```bash
codeagent chat --debug
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.