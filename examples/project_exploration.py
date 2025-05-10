"""Example of using CodeAgent to explore a project"""
import os
from pathlib import Path
import tempfile
import shutil
import sys

# Add parent directory to path to import codeagent
sys.path.insert(0, str(Path(__file__).parent.parent))

from codeagent.agent.code_agent import CodeAgent

def main():
    """Run a project exploration example"""
    # Create a temporary directory for the example project
    example_dir = tempfile.mkdtemp()
    print(f"Created example project directory: {example_dir}")
    
    try:
        # Create a more complex project structure
        create_example_project(example_dir)
        
        # Initialize the agent
        agent = CodeAgent(example_dir, verbose=True)
        
        # Define an exploration task
        task = "Explore this codebase and explain what it does. Focus on the architecture, data models, and key functionality."
        
        print(f"\nExecuting task: {task}\n")
        
        # Process the task
        analysis = agent.process_task(task)
        
        # Print the analysis
        print("\nProject Analysis:")
        print("-" * 50)
        print(analysis)
        print("-" * 50)
        
    finally:
        # Clean up
        shutil.rmtree(example_dir)
        print(f"Cleaned up example project directory: {example_dir}")

def create_example_project(project_dir):
    """Create a more complex project structure for the example"""
    # Create directories
    os.makedirs(os.path.join(project_dir, "src"))
    os.makedirs(os.path.join(project_dir, "src", "models"))
    os.makedirs(os.path.join(project_dir, "src", "controllers"))
    os.makedirs(os.path.join(project_dir, "src", "views"))
    os.makedirs(os.path.join(project_dir, "src", "utils"))
    os.makedirs(os.path.join(project_dir, "tests"))
    os.makedirs(os.path.join(project_dir, "docs"))
    
    # Create .agent.md file
    with open(os.path.join(project_dir, ".agent.md"), "w") as f:
        f.write("""# Example Project

## Project Description
A small web application using a Model-View-Controller (MVC) architecture.

## Architecture
The application follows a classic MVC pattern:
- Models: Data structures and business logic
- Views: User interface templates
- Controllers: Handle requests and coordinate models and views

## Code Style
PEP 8 for Python code.

## Common Commands
- Run: `python -m src.app`
- Test: `pytest`
- Lint: `flake8 src`

## File Descriptions
- `src/`: Source code directory
- `src/models/`: Data models
- `src/controllers/`: Request handlers
- `src/views/`: UI templates
- `src/utils/`: Utility functions
- `tests/`: Test directory
- `docs/`: Documentation
- `README.md`: Project documentation
""")
    
    # Create app.py
    with open(os.path.join(project_dir, "src", "app.py"), "w") as f:
        f.write("""#!/usr/bin/env python
\"\"\"Main application entry point\"\"\"
from src.controllers.user_controller import UserController
from src.controllers.post_controller import PostController

def main():
    \"\"\"Initialize and start the application\"\"\"
    # Initialize controllers
    user_controller = UserController()
    post_controller = PostController()
    
    # Demo user operations
    user = user_controller.create_user("john_doe", "john@example.com")
    print(f"Created user: {user}")
    
    # Demo post operations
    post = post_controller.create_post(user["id"], "Hello, World!", "This is my first post.")
    print(f"Created post: {post}")
    
    all_posts = post_controller.get_posts_by_user(user["id"])
    print(f"User posts: {all_posts}")

if __name__ == "__main__":
    main()
""")
    
    # Create models
    with open(os.path.join(project_dir, "src", "models", "__init__.py"), "w") as f:
        f.write("")
    
    with open(os.path.join(project_dir, "src", "models", "user.py"), "w") as f:
        f.write("""\"\"\"User model\"\"\"
import uuid
from datetime import datetime

class User:
    \"\"\"User model representing application users\"\"\"
    
    def __init__(self, username, email):
        \"\"\"Initialize a new user\"\"\"
        self.id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.created_at = datetime.now()
        self.posts = []
    
    def to_dict(self):
        \"\"\"Convert user to dictionary\"\"\"
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "post_count": len(self.posts)
        }
    
    def add_post(self, post):
        \"\"\"Add a post to the user\"\"\"
        self.posts.append(post.id)
""")
    
    with open(os.path.join(project_dir, "src", "models", "post.py"), "w") as f:
        f.write("""\"\"\"Post model\"\"\"
import uuid
from datetime import datetime

class Post:
    \"\"\"Post model representing user posts\"\"\"
    
    def __init__(self, user_id, title, content):
        \"\"\"Initialize a new post\"\"\"
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.title = title
        self.content = content
        self.created_at = datetime.now()
        self.likes = 0
    
    def to_dict(self):
        \"\"\"Convert post to dictionary\"\"\"
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "likes": self.likes
        }
    
    def like(self):
        \"\"\"Increment post likes\"\"\"
        self.likes += 1
""")
    
    # Create controllers
    with open(os.path.join(project_dir, "src", "controllers", "__init__.py"), "w") as f:
        f.write("")
    
    with open(os.path.join(project_dir, "src", "controllers", "user_controller.py"), "w") as f:
        f.write("""\"\"\"User controller\"\"\"
from src.models.user import User
from src.utils.database import Database

class UserController:
    \"\"\"Controller for user operations\"\"\"
    
    def __init__(self):
        \"\"\"Initialize controller\"\"\"
        self.db = Database()
    
    def create_user(self, username, email):
        \"\"\"Create a new user\"\"\"
        # Check if username already exists
        if self.db.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")
        
        # Create and store user
        user = User(username, email)
        self.db.save_user(user)
        
        return user.to_dict()
    
    def get_user(self, user_id):
        \"\"\"Get user by ID\"\"\"
        user = self.db.get_user(user_id)
        if user:
            return user.to_dict()
        return None
    
    def get_all_users(self):
        \"\"\"Get all users\"\"\"
        users = self.db.get_all_users()
        return [user.to_dict() for user in users]
""")
    
    with open(os.path.join(project_dir, "src", "controllers", "post_controller.py"), "w") as f:
        f.write("""\"\"\"Post controller\"\"\"
from src.models.post import Post
from src.utils.database import Database

class PostController:
    \"\"\"Controller for post operations\"\"\"
    
    def __init__(self):
        \"\"\"Initialize controller\"\"\"
        self.db = Database()
    
    def create_post(self, user_id, title, content):
        \"\"\"Create a new post\"\"\"
        # Check if user exists
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User with ID '{user_id}' not found")
        
        # Create and store post
        post = Post(user_id, title, content)
        self.db.save_post(post)
        
        # Add post to user
        user.add_post(post)
        self.db.update_user(user)
        
        return post.to_dict()
    
    def get_post(self, post_id):
        \"\"\"Get post by ID\"\"\"
        post = self.db.get_post(post_id)
        if post:
            return post.to_dict()
        return None
    
    def get_posts_by_user(self, user_id):
        \"\"\"Get all posts by a user\"\"\"
        posts = self.db.get_posts_by_user(user_id)
        return [post.to_dict() for post in posts]
    
    def like_post(self, post_id):
        \"\"\"Like a post\"\"\"
        post = self.db.get_post(post_id)
        if not post:
            raise ValueError(f"Post with ID '{post_id}' not found")
        
        post.like()
        self.db.update_post(post)
        
        return post.to_dict()
""")
    
    # Create utils
    with open(os.path.join(project_dir, "src", "utils", "__init__.py"), "w") as f:
        f.write("")
    
    with open(os.path.join(project_dir, "src", "utils", "database.py"), "w") as f:
        f.write("""\"\"\"In-memory database utility\"\"\"

class Database:
    \"\"\"Simple in-memory database\"\"\"
    
    _instance = None
    
    def __new__(cls):
        \"\"\"Singleton pattern\"\"\"
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.users = {}
            cls._instance.posts = {}
        return cls._instance
    
    def save_user(self, user):
        \"\"\"Save a user\"\"\"
        self.users[user.id] = user
    
    def get_user(self, user_id):
        \"\"\"Get user by ID\"\"\"
        return self.users.get(user_id)
    
    def get_user_by_username(self, username):
        \"\"\"Get user by username\"\"\"
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def update_user(self, user):
        \"\"\"Update a user\"\"\"
        if user.id in self.users:
            self.users[user.id] = user
    
    def get_all_users(self):
        \"\"\"Get all users\"\"\"
        return list(self.users.values())
    
    def save_post(self, post):
        \"\"\"Save a post\"\"\"
        self.posts[post.id] = post
    
    def get_post(self, post_id):
        \"\"\"Get post by ID\"\"\"
        return self.posts.get(post_id)
    
    def update_post(self, post):
        \"\"\"Update a post\"\"\"
        if post.id in self.posts:
            self.posts[post.id] = post
    
    def get_posts_by_user(self, user_id):
        \"\"\"Get all posts by a user\"\"\"
        return [post for post in self.posts.values() if post.user_id == user_id]
""")
    
    # Create views directory with a placeholder
    with open(os.path.join(project_dir, "src", "views", "__init__.py"), "w") as f:
        f.write("")
    
    with open(os.path.join(project_dir, "src", "views", "placeholder.txt"), "w") as f:
        f.write("""This is a placeholder for UI templates.
In a real application, this directory would contain HTML, CSS, and JavaScript files.
""")
    
    # Create README.md
    with open(os.path.join(project_dir, "README.md"), "w") as f:
        f.write("""# Example MVC Application

A simple web application using a Model-View-Controller (MVC) architecture.

## Features

- User management
- Post creation and retrieval
- Likes functionality

## Project Structure

- `src/`: Source code directory
  - `models/`: Data models
  - `controllers/`: Request handlers
  - `views/`: UI templates (placeholder)
  - `utils/`: Utility functions
- `tests/`: Test directory
- `docs/`: Documentation

## Running the Application

```bash
python -m src.app          
""")
if name == "main":
main()