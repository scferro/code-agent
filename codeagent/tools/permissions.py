"""Universal permission system for tools that modify files or run commands."""
import sys
import os
from rich.console import Console

# Global variable to store the status context when we need to pause it
_current_status = None

def set_status_context(status_context):
    """Set the current Rich status context so we can pause it during permission requests."""
    global _current_status
    _current_status = status_context

def request_permission(operation_type: str, description: str, details: str = None, diff: str = None) -> bool:
    """Request permission from the user for potentially dangerous operations.
    
    Args:
        operation_type: Type of operation (e.g., 'write', 'edit', 'execute')
        description: Brief description of what will be done
        details: Additional details about the operation
        diff: Optional diff/preview of changes to be made
        
    Returns:
        bool: True if permission granted, False otherwise
    """
    # Temporarily stop the Rich status if it's running
    global _current_status
    status_was_running = False
    if _current_status:
        try:
            _current_status.stop()
            status_was_running = True
        except:
            pass
    
    # Clear the console status line and move cursor
    print("\r\033[K", end="")  # Clear current line
    sys.stdout.flush()
    sys.stderr.flush()
    
    print("\n" + "="*60)
    print(f"🔐 PERMISSION REQUEST: {operation_type.upper()}")
    print("="*60)
    print(f"Operation: {description}")
    if details:
        print(f"Details: {details}")
    
    if diff:
        print("\nChanges to be made:")
        print("-" * 40)
        print(diff)
        print("-" * 40)
    
    print("\nDo you want to allow this operation?")
    
    while True:
        try:
            # Force flush before input
            sys.stdout.flush()
            sys.stderr.flush()
            response = input("Enter 'y' for yes or 'n' for no: ").strip().lower()
            if response in ['y', 'yes']:
                print("✅ Permission granted")
                result = True
                break
            elif response in ['n', 'no']:
                print("❌ Permission denied")
                result = False
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Permission denied (interrupted)")
            result = False
            break
    
    # Restart the Rich status if it was running
    if status_was_running and _current_status:
        try:
            _current_status.start()
        except:
            pass
    
    return result