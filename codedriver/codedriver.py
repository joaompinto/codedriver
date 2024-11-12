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
from datetime import datetime
from rich.table import Table

# Change relative imports to absolute
from codedriver.cli.info import info_command
from codedriver.cli.change import execute as change_command  # Import the execute function as change_command

console = Console()

def get_preview_directory() -> str:
    """Generate a unique preview directory path"""
    return tempfile.mkdtemp(prefix="codedriver_preview_")


def set_llm_command(args):
    """Set the active LLM"""
    from .llms.registry import LLMRegistry
    registry = LLMRegistry()
    current = registry.get_current_llm()
    if current:
        registry.record_switch(current, args.llm_name)
    else:
        registry.record_switch("none", args.llm_name)
    console.print(f"[green]Set active LLM to: {args.llm_name}[/green]")


def format_wait_time(seconds: int) -> str:
    """Format wait time in a human readable way"""
    if seconds < 60:
        return f"{seconds} seconds"
    mins = seconds // 60
    if mins < 60:
        return f"{mins} minutes"
    return f"{mins // 60} hours and {mins % 60} minutes"

def status_command(args):
    """Show status of all configured LLMs"""
    from .llms.registry import LLMRegistry
    from .llms.claude_sonnet import ClaudeSonnet
    from .llms.google_gemini import GeminiPro

    registry = LLMRegistry()
    current = registry.get_current_llm()
    
    # Create status table
    table = Table(title="LLM Status")
    table.add_column("LLM", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Current", style="yellow")
    
    llms = [ClaudeSonnet(), GeminiPro()]
    
    for llm in llms:
        limit_info = registry.get_rate_limit_info(llm.name)
        status = "Available"
        
        if limit_info:
            available_at = datetime.fromisoformat(limit_info["until"])
            wait_time = (available_at - datetime.now()).total_seconds()
            if wait_time > 0:
                status = f"Rate limited ({format_wait_time(int(wait_time))} remaining)"
                style = "red"
            else:
                status = "Available"
                style = "green"
        else:
            style = "green"
            
        is_current = "→" if llm.name == current else ""
        table.add_row(llm.name, status, is_current, style=style)
    
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="CodeDriver CLI")
    
    # Add global verbose flag that will be inherited by subcommands
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed debug information")
    subparsers = parser.add_subparsers(dest="command")

    # Info command
    parser_info = subparsers.add_parser("info", help="Display info about the codebase")
    parser_info.add_argument("--request", "-r", help="Additional analysis request")
    parser_info.add_argument("--verbose", "-v", action="store_true", help="Show detailed debug information")
    parser_info.set_defaults(func=lambda args: info_command(args))

    # Change command
    parser_change = subparsers.add_parser("change", help="Get suggested code changes")
    parser_change.add_argument("text", help="Description of the changes needed")
    parser_change.add_argument("--verbose", "-v", action="store_true", help="Show detailed debug information")
    parser_change.set_defaults(func=lambda args: change_command(args.text, verbose=args.verbose))

    # Add set-llm command
    parser_set_llm = subparsers.add_parser("set-llm", help="Set the active LLM")
    parser_set_llm.add_argument("llm_name", choices=["Claude-3 Sonnet", "Gemini Pro"], 
                               help="Name of the LLM to use")
    parser_set_llm.set_defaults(func=set_llm_command)

    # Add status command
    parser_status = subparsers.add_parser("status", help="Show LLM availability status")
    parser_status.set_defaults(func=status_command)

    args = parser.parse_args()
    if args.command:
        # Use either global or command-specific verbose flag
        if hasattr(args, 'verbose'):
            args.verbose = args.verbose or getattr(parser.parse_args([]), 'verbose', False)
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()