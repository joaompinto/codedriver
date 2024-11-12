"""
CodeDriver - A tool for AI-assisted code modifications

Flow:
1. Command Line Interface
   - 'info' command: Analyzes and summarizes project
   - 'change' command: Processes code modification requests

2. File Processing
   - Scans directory for code files (.py, .js, .ts, etc.)
   - Reads file contents
   - Creates backups before modifications

3. AI Integration
   - Uses Claude API (via ClaudeAPI class) for code analysis
   - Sends file contents and change requests to AI
   - Receives structured responses with file modifications

4. Change Management
   - Creates preview directory for testing changes
   - Displays detailed diffs of proposed changes
   - Allows selective application of changes
   - Supports:
     * Full change preview
     * Individual file changes
     * Diff viewing
     * Change confirmation

5. Safety Features
   - Creates backups before modifications
   - Uses preview directory for testing
   - Applies changes through patch system
   - Validates file integrity
"""

import argparse
import tempfile
from rich.console import Console

from .cli.info import info_command
from .cli.change import execute as change_command  # Import the execute function as change_command

console = Console()

def get_preview_directory() -> str:
    """Generate a unique preview directory path"""
    return tempfile.mkdtemp(prefix="codedriver_preview_")


def main():
    parser = argparse.ArgumentParser(description="CodeDriver CLI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed debug information")
    subparsers = parser.add_subparsers(dest="command")

    # Info command registration with verbose flag
    parser_info = subparsers.add_parser("info", help="Display info about the codebase")
    parser_info.add_argument("--request", "-r", help="Additional analysis request")
    parser_info.set_defaults(func=lambda args: info_command(args))
    
    # Change command now uses the imported function
    parser_change = subparsers.add_parser("change", help="Get suggested code changes")
    parser_change.add_argument("text", help="Description of the changes needed")
    parser_change.set_defaults(func=lambda args: change_command(args.text, verbose=args.verbose))

    args = parser.parse_args()
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()