from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
import os
from typing import Dict, Any
import json
import xml.etree.ElementTree as ET
from io import StringIO

from ..agent import LLMAgent  # Update import
from ..testing import (
    show_file_diff,
    apply_changes_to_preview,
    apply_changes_to_working
)
from ..scan import (
    collect_files,
    generate_files_summary
)

console = Console()

def call_claude_with_progress(prompt: str, progress: Progress, message: str = "Waiting for response...", verbose: bool = False) -> Dict[Any, Any]:
    """Utility function to call LLM Agent with progress indicator"""
    task = progress.add_task(message, total=None)
    agent = LLMAgent()
    response = agent.send_message(prompt, verbose=verbose)
    progress.update(task, visible=False)
    return response

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

def display_changes(modified_files: list[str]) -> list[str]:
    """Display changes using rich formatted output"""
    # Display the overview
    console.print("\n[yellow]Changes Overview:[/yellow]")
    console.print("\n[blue]Files to be modified:[/blue]")
    
    # Add file counter for selection
    for idx, filepath in enumerate(modified_files, 1):
        console.print(f"  📄 [{idx}] {filepath}")
        if os.path.exists(filepath):
            preview_path = os.path.join(os.path.dirname(filepath), filepath)
            current_lines = get_file_line_count(filepath)
            new_lines = get_file_line_count(preview_path)
            added = max(0, new_lines - current_lines)
            removed = max(0, current_lines - new_lines)
            
            if added or removed:
                changes = []
                if added:
                    changes.append(f"[green]+{added}[/green]")
                if removed:
                    changes.append(f"[red]-{removed}[/red]")
                console.print(f"    Lines: {' '.join(changes)}")
        else:
            console.print(f"    [green]New file[/green]")
    
    return modified_files

def describe_change(text: str, progress: Progress, verbose: bool = False) -> tuple[str, bool]:
    """Get Claude's interpretation of the change request and validation status"""
    prompt = """Please analyze this code change request:

{}

In 2-3 sentences, explain what changes are needed.
End with exactly "STATUS: OK" if the request is clear and specific enough to act on, 
or "STATUS: NOK" if the request is unclear or ambiguous.""".format(text)

    response = call_claude_with_progress(prompt, progress, "Analyzing request...", verbose=verbose)
    if "content" in response and len(response["content"]) > 0:
        content = response["content"][0]["text"]
        # Check last line for status
        status_ok = content.strip().endswith("STATUS: OK")
        # Remove status line from displayed content
        interpretation = content.rsplit("\n", 1)[0].strip()
        return interpretation, status_ok
    return "Could not get interpretation of change request.", False

def execute(text: str, verbose: bool = False):
    """Execute the change command"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Only collect file paths, not contents
        files_content, _, unhandled_files = collect_files(progress)
        file_paths = [f.split('\n')[0].replace('File: ', '').strip() for f in files_content]

        if unhandled_files:
            progress.stop()
            console.print("\n[red]Error: Cannot proceed with unhandled files present[/red]")
            console.print("[yellow]Add these extensions to FILE_HANDLERS in scan.py to process them[/yellow]")
            return

        if not file_paths:
            progress.stop()
            console.print("[red]No code files found in the current directory.[/red]")
            return

        # Display identified files
        console.print("\n[blue]Files identified for processing:[/blue]")
        for filepath in file_paths:
            console.print(f"  📄 {filepath}")

        # Get interpretation and validation status using the same progress context
        interpretation, is_valid = describe_change(text, progress, verbose=verbose)
        progress.stop()  # Stop progress before printing panels
        
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
        # Only collect file paths, not contents
        files_content, _, unhandled_files = collect_files(progress)
        file_paths = [f.split('\n')[0].replace('File: ', '').strip() for f in files_content]

        if unhandled_files:
            progress.stop()
            console.print("\n[red]Error: Cannot proceed with unhandled files present[/red]")
            console.print("[yellow]Add these extensions to FILE_HANDLERS in scan.py to process them[/yellow]")
            return

        if not file_paths:
            progress.stop()
            console.print("[red]No code files found in the current directory.[/red]")
            return

        # Initialize Claude and process changes
        claude = LLMAgent()  # Changed from ClaudeAPI
        claude.set_files_to_process(file_paths)
        
        # Process with Claude
        response = claude.process_changes(text, verbose=verbose)
        progress.stop()  # Stop before any console output

        if "content" in response and len(response["content"]) > 0:
            changes_content = response["content"][0]["text"]
            
            # Use public API to check for changes first
            preview_dir, test_cmds, modified_files, preview_success = apply_changes_to_preview(changes_content)
            
            # Check for actual changes before proceeding with display
            if not preview_success and preview_dir:  # preview_dir check ensures it's not a failure
                console.print("[yellow]No changes needed - Claude's output matches current files.[/yellow]")
                return
                
            if not preview_success:
                console.print("\n[red]Failed to apply changes to preview directory[/red]")
                return
                
            # Exit early if no files were modified
            if not modified_files:
                console.print("[yellow]No files were modified - nothing to apply.[/yellow]")
                return
            
            # Use the preview directory changes for display
            files_to_modify = display_changes(modified_files)
            
            # Add preview directory info before options
            console.print("\n[blue]Preview Directory:[/blue]")
            console.print(f"Changes are staged in: [cyan]{preview_dir}[/cyan]")
                
            while True:
                # Show compact options
                console.print("\n" + "─" * 80)
                console.print("[yellow]Options:[/yellow] [green]y[/green]=apply all, [blue]d[/blue]=view diff, [yellow]number[/yellow]=apply specific file, [red]q[/red]=quit")
                choice = console.input("\n> ").lower()
                
                if choice == 'q':
                    console.print("\n[yellow]Operation cancelled - no changes were made.[/yellow]")
                    return
                elif choice == 'd':
                    for file in files_to_modify:
                        console.print(f"\n[blue]Diff for {file}:[/blue]")
                        show_file_diff(os.path.join(".", file), os.path.join(preview_dir, file))
                    continue
                elif choice == 'y':
                    selected_files = files_to_modify
                    break
                elif choice.isdigit():
                    file_idx = int(choice)
                    if 1 <= file_idx <= len(files_to_modify):
                        selected_files = [files_to_modify[file_idx - 1]]
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