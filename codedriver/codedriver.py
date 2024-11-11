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
import json
import os
from typing import Any, Dict

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.layout import Layout
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agent import ClaudeAPI
from .testing import (
    apply_changes, 
    test_changes, 
    show_diff,
    show_directory_diff,
    apply_changes_to_preview,
    apply_changes_to_working
)

console = Console()


def get_file_content(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"


def call_claude_with_progress(prompt: str, progress: Progress, message: str = "Waiting for response...") -> Dict[Any, Any]:
    """Utility function to call Claude API with progress indicator"""
    task = progress.add_task(message, total=None)
    claude = ClaudeAPI()
    response = claude.send_message(prompt)
    progress.update(task, visible=False)
    return response


def info(args=None):  # Accept an optional argument
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Collect all file contents
        files_content = []
        console.print("\n[blue]Files being processed:[/blue]")
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(
                    (".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go")
                ):
                    path = os.path.join(root, file)
                    console.print(f"📄 {path}")
                    content = get_file_content(path)
                    files_content.append(f"File: {path}\n\n{content}\n")

        if not files_content:
            print("No code files found in the current directory.")
            return

        # Prepare prompt for Claude
        base_prompt = """Please analyze these code files and provide a concise summary of:
1. The main purpose of the application
2. Key features and functionality
3. Main components and their roles"""

        if args and args.request:
            base_prompt += f"\n\nAdditionally, please address this specific request:\n{args.request}"

        prompt = base_prompt + "\n\nHere are the files:\n\n{}".format("\n---\n".join(files_content))

        try:
            response = call_claude_with_progress(prompt, progress, "Analyzing project...")

            if "content" in response and len(response["content"]) > 0:
                print("\nProject Analysis:")
                markdown = Markdown(response["content"][0]["text"])
                console.print(markdown)
            else:
                print("Error: No content in response")
                print("Raw response:", json.dumps(response, indent=2))
        except Exception as e:
            print(f"Error getting analysis: {str(e)}")


def get_absolute_path(filepath: str) -> str:
    """Convert relative path to absolute path"""
    return os.path.abspath(filepath)

def get_relative_path(filepath: str) -> str:
    """Convert absolute path to relative path from working directory"""
    try:
        return os.path.relpath(filepath)
    except ValueError:
        return filepath

def get_file_line_count(filepath: str) -> int:
    """Get the number of lines in a file"""
    try:
        with open(filepath, 'r') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def get_content_line_count(content: str) -> int:
    """Get the number of lines in content string"""
    return len(content.split('\n'))

def display_changes(request_text: str, changes_content: str) -> None:
    """Display changes using rich formatted output"""
    # Extract files and their content that will be modified
    files_to_modify = {}
    current_file = None
    current_content = []
    
    for line in changes_content.split('\n'):
        if line.startswith('### ['):
            if current_file:
                files_to_modify[current_file] = '\n'.join(current_content)
            current_file = line.replace('### [', '').replace(']', '').strip()
            current_content = []
        else:
            current_content.append(line)
            
    if current_file:
        files_to_modify[current_file] = '\n'.join(current_content)

    # Display the overview
    console.print("\n[yellow]Changes Overview:[/yellow]")
    console.print("\n[blue]Files to be modified:[/blue]")
    
    # Add file counter for selection
    for idx, (filepath, new_content) in enumerate(files_to_modify.items(), 1):
        console.print(f"  📄 [{idx}] {filepath}")
        if os.path.exists(filepath):
            current_lines = get_file_line_count(filepath)
            new_lines = get_content_line_count(new_content)
            added = max(0, new_lines - current_lines)
            removed = max(0, current_lines - new_lines)
            
            if added or removed:
                changes = []
                if added:
                    changes.append(f"[green]+{added}[/green]")
                if removed:
                    changes.append(f"[red]-{removed}[/red]")
                console.print(f"    Lines: {' '.join(changes)}")
            console.print("    [yellow]⚠ This file will be replaced[/yellow]")
        else:
            console.print(f"    [green]+{get_content_line_count(new_content)} lines[/green] (new file)")
            
    # Show the original request
    console.print("\n[blue]Requested changes:[/blue]")
    console.print(Panel(request_text, title="Change Request", border_style="yellow"))
    
    # Show compact options
    console.print("\n" + "─" * 80)
    console.print("[yellow]Options:[/yellow] [green]y[/green]=apply all, [blue]d[/blue]=view diff, [yellow]number[/yellow]=apply specific file, [red]q[/red]=quit")
    
    return files_to_modify

def generate_files_summary(files_content: list) -> str:
    """Generate a summary of files being processed"""
    summary = "Files being processed:\n\n"
    for file_content in files_content:
        # Extract filename and count lines
        filename = file_content.split('\n')[0].replace('File: ', '')
        rel_path = get_relative_path(filename)
        code_lines = len(file_content.split('\n')) - 3
        summary += f"📄 {rel_path} ({code_lines} lines)\n"
    return summary


def collect_files(progress) -> list:
    """Collect all code files with progress indicator"""
    task = progress.add_task("Scanning files...", total=None)
    files_content = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(
                (".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go")
            ):
                path = os.path.join(root, file)
                content = get_file_content(path)
                files_content.append(f"File: {path}\n\n{content}\n")
    progress.update(task, visible=False)
    return files_content

def describe_change(text: str) -> tuple[str, bool]:
    """Get Claude's interpretation of the change request and validation status"""
    prompt = """I need to understand how to apply this change request to a software project:

{}

Please analyze and:
1. Explain what changes would be needed
2. List files that might be affected
3. Note any potential risks
4. End with exactly "STATUS: OK" if the request is clear and actionable, 
   or "STATUS: NOK" if the request is unclear, risky, or not actionable.

Keep the response concise.""".format(text)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        response = call_claude_with_progress(prompt, progress, "Analyzing request...")
        if "content" in response and len(response["content"]) > 0:
            content = response["content"][0]["text"]
            # Check last line for status
            status_ok = content.strip().endswith("STATUS: OK")
            # Remove status line from displayed content
            interpretation = content.rsplit("\n", 1)[0].strip()
            return interpretation, status_ok
        return "Could not get interpretation of change request.", False

def change(text: str):
    # Get interpretation and validation status
    interpretation, is_valid = describe_change(text)
    console.print("\n[blue]Change Request Interpretation:[/blue]")
    console.print(Panel(interpretation, title="AI Analysis", border_style="blue"))
    
    if not is_valid:
        if not Confirm.ask("\n[yellow]⚠ Change request may be unclear or risky. Proceed anyway?[/yellow]"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
    else:
        console.print("\n[green]✓ Change request validated[/green]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        files_content = collect_files(progress)

        if not files_content:
            progress.stop()
            console.print("[red]No code files found in the current directory.[/red]")
            return

        # Generate files summary first
        summary_text = generate_files_summary(files_content)
        
        # Process with Claude
        prompt = """I need help modifying some code files. Here are the current files:

{}

The requested changes are:
{}

Format your response with the full content of the modified files, each starting with a header in the format:
### [filepath]
Where filepath should be a relative path from the current directory, for example:
### [codedriver/agent.py]
<full content of the modified file>

Important: Use relative paths from the current directory, do not use absolute paths or ./path/to/file.py
""".format("\n---\n".join(files_content), text)

        # Display the request details before processing
        console.print("\n[blue]Request Details:[/blue]")
        console.print(Panel(summary_text, title="Files to Process", border_style="blue"))
        console.print(Panel(text, title="Requested Changes", border_style="yellow"))
        
        try:
            response = call_claude_with_progress(prompt, progress, "Analyzing changes...")
            progress.stop()  # Stop before any console output
            
            if "content" in response and len(response["content"]) > 0:
                changes_content = response["content"][0]["text"]
                files_to_modify = display_changes(text, changes_content)
                
                # Use public API instead of internal functions
                preview_dir, test_cmds, modified_files, preview_success = apply_changes_to_preview(changes_content)
                
                if not preview_success:
                    console.print("\n[red]Failed to apply changes to preview directory[/red]")
                    return
                    
                while True:
                    # Show compact options
                    console.print("\n" + "─" * 80)
                    console.print("[yellow]Options:[/yellow] [green]y[/green]=apply all, [blue]d[/blue]=view diff, [yellow]number[/yellow]=apply specific file, [red]q[/red]=quit")
                    choice = console.input("\n> ").lower()
                    
                    if choice == 'q':
                        console.print("\n[yellow]Operation cancelled - no changes were made.[/yellow]")
                        return
                    elif choice == 'd':
                        show_directory_diff(".", preview_dir)
                        continue
                    elif choice == 'y':
                        selected_files = list(files_to_modify.keys())
                        break
                    elif choice.isdigit():
                        file_idx = int(choice)
                        if 1 <= file_idx <= len(files_to_modify):
                            selected_files = [list(files_to_modify.keys())[file_idx - 1]]
                            break
                        else:
                            console.print("[red]Invalid file number[/red]")
                            continue
                    else:
                        console.print("[red]Invalid choice[/red]")
                        continue
                
                # Apply selected changes using patch-based function
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as apply_progress:
                    task = apply_progress.add_task("Applying changes...", total=1)
                    if apply_changes_to_working(preview_dir, selected_files):
                        apply_progress.update(task, advance=1)
                        console.print("\n[green]✓ Changes applied successfully![/green]")
                    else:
                        console.print("\n[red]✗ Failed to apply changes.[/red]")

            else:
                console.print("[red]Error: No content in response[/red]")
                console.print("Raw response:", json.dumps(response, indent=2))
        except Exception as e:
            progress.stop()  # Stop in error case
            console.print(f"[red]Error getting changes: {str(e)}[/red]")
            # Add backup restoration hint
            console.print("[yellow]Tip: You can find backups in your temp directory if needed.[/yellow]")
            return


def main():
    parser = argparse.ArgumentParser(description="CodeDriver CLI")
    subparsers = parser.add_subparsers(dest="command")

    parser_info = subparsers.add_parser("info", help="Display info about the codebase")
    parser_info.add_argument("--request", "-r", help="Additional analysis request")
    parser_info.set_defaults(func=info)

    parser_change = subparsers.add_parser(
        "change", help="Get suggested code changes"
    )  # Updated command name
    parser_change.add_argument("text", help="Description of the changes needed")
    parser_change.set_defaults(
        func=lambda args: change(args.text)
    )  # Updated function reference

    args = parser.parse_args()
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
