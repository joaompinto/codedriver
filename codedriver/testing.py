import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from rich.console import Console
from rich.syntax import Syntax
import difflib
from pathlib import Path
from .scan import _load_gitignore, _is_ignored
import re

console = Console()

def _copy(src: str, dst: str, is_dir: bool = False, silent: bool = False) -> None:
    """Helper function to perform copy operations"""
    # Load gitignore patterns
    ignore_patterns = _load_gitignore()
    
    if _is_ignored(src, ignore_patterns):
        return
        
    if not silent:
        rel_src = os.path.relpath(src)
        rel_dst = os.path.relpath(dst)
        
        if os.path.exists(dst):
            console.print(f"[yellow]Replacing[/yellow] {rel_dst}")
        else:
            console.print(f"[green]Creating[/green] {rel_dst}")
        
    if is_dir:
        def _ignore_func(path, names):
            return [n for n in names if n == '.git' or 
                   _is_ignored(os.path.join(path, n), ignore_patterns)]
                   
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_func)
    else:
        shutil.copy2(src, dst)

def _ignore_patterns(path, names):
    """Helper function for ignoring .git directories"""
    return [n for n in names if n == '.git']

def _create_backup() -> str:
    """Create a backup of the working directory"""
    backup_dir = tempfile.mkdtemp(prefix="codedriver_backup_")
    
    try:
        console.print("[blue]Creating backup...[/blue]")
        _copy(".", backup_dir, is_dir=True, silent=True)
        console.print(f"[dim]Backup created at: {backup_dir}[/dim]")
        return backup_dir
    except Exception as e:
        console.print(f"[red]Error creating backup:[/red] {str(e)}")
        return ""

def _process_changes(content: str, preview_dir: str) -> tuple[list, list]:
    """Process changes using delimiter-based format"""
    test_cmds = []
    modified_files = []
    
    try:
        # Extract file changes using regex
        file_pattern = (
            r'@==CODEDRIVER==.*?==@\s*FILE\s+(MODIFY|CREATE|DELETE)\s+([^\s]+)\s+([a-f0-9]{8})\s*\n(.*?)\n\s*@==CODEDRIVER==.*?==@\s*FILE'
        )
        
        # Find all file changes in the content
        for match in re.finditer(file_pattern, content, re.DOTALL):
            operation = match.group(1).lower()
            filepath = match.group(2).strip()
            provided_hash = match.group(3)
            file_content = match.group(4).strip()
            
            # Process file content for test commands
            for line in file_content.split('\n'):
                if line.startswith('"""TEST CMD:'):
                    test_cmds.append(line.split(":", 1)[1].strip().strip('"""'))
            
            # Skip if hash verification fails
            if operation != "delete":
                content_hash = hashlib.md5(file_content.encode('utf-8')).hexdigest()[:8]
                if content_hash != provided_hash:
                    console.print(f"[red]Warning: Content verification failed for {filepath}[/red]")
                    continue

            # Process the change
            if operation in ["modify", "create"]:
                # Create parent directories if needed
                full_path = os.path.join(preview_dir, filepath)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write content to preview file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                
                modified_files.append(filepath)

            elif operation == "delete" and os.path.exists(filepath):
                modified_files.append(filepath)

    except Exception as e:
        console.print(f"[red]Error processing changes:[/red] {str(e)}")
        
    return test_cmds, modified_files

def _setup_preview_dir() -> str:
    """Setup and return the preview directory path"""
    from .codedriver import get_preview_directory
    
    preview_dir = get_preview_directory()
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir)
    os.makedirs(preview_dir)
    
    # Copy current directory content silently
    for item in os.listdir("."):
        if item == '.git':
            continue
        s = os.path.join(".", item)
        d = os.path.join(preview_dir, item)
        _copy(s, d, is_dir=os.path.isdir(s), silent=True)
            
    return preview_dir

def apply_changes_to_working(preview_dir: str, modified_files: list, backup_first: bool = True) -> bool:
    """Apply changes from preview directory to working directory by fully updating the modified files"""
    try:
        if backup_first:
            backup_dir = _create_backup()
            if not backup_dir:
                console.print("[red]Failed to create backup, aborting changes[/red]")
                return False
                
            console.print(f"\n[blue]Backup created at:[/blue] {backup_dir}")
            console.print("[dim]You can restore from this backup if needed[/dim]")

        console.print("\n[blue]Applying changes to working directory...[/blue]")
        
        if not modified_files:
            console.print("[yellow]No files to modify[/yellow]")
            return True
            
        for file in modified_files:
            preview_path = os.path.join(preview_dir, file)
            working_path = os.path.join(".", file)
            
            # Create parent directories if needed
            os.makedirs(os.path.dirname(working_path), exist_ok=True)
            
            # Copy file from preview directory to working directory
            shutil.copy2(preview_path, working_path)
            console.print(f"[green]Updated:[/green] {working_path}")
            
        console.print("[green]✓ Changes applied successfully[/green]")
        return True

    except Exception as e:
        console.print(f"[red]Error applying changes to working directory:[/red] {str(e)}")
        return False

def apply_changes_to_preview(content: str) -> tuple[str, list, list, bool]:
    """Apply changes to preview directory and return preview dir path, test commands, and modified files"""
    try:
        preview_dir = _setup_preview_dir()
        test_cmds, modified_files = _process_changes(content, preview_dir)

        if not modified_files:
            console.print("[yellow]No files to modify[/yellow]")
            return preview_dir, test_cmds, modified_files, True
        console.print(f"\n[blue]Changes applied to preview directory:[/blue] {preview_dir}")

        # Run collected test commands
        for cmd in test_cmds:
            console.print(f"\n[yellow]Running test command:[/yellow] {cmd}")
            result = subprocess.run(cmd, shell=True, cwd=preview_dir, capture_output=True, text=True)
            if result.stdout:
                console.print("[green]Output:[/green]\n" + result.stdout)
            if result.stderr:
                console.print("[red]Errors:[/red]\n" + result.stderr)
            if result.returncode != 0:
                console.print(f"[red]✗ Test command failed:[/red] {cmd}")
                return preview_dir, test_cmds, modified_files, False

        return preview_dir, test_cmds, modified_files, True

    except Exception as e:
        console.print(f"[red]Error applying changes to preview:[/red] {str(e)}")
        return "", [], [], False

def apply_changes(content: str) -> bool:
    """Apply the changes to preview directory and then working directory"""
    preview_dir, test_cmds, modified_files, preview_success = apply_changes_to_preview(content)
    
    if not preview_success or not preview_dir:
        return False
        
    return apply_changes_to_working(preview_dir, modified_files)

def test_changes(content: str) -> bool:
    """Test the changes without applying them to working directory"""
    preview_dir, _, _, preview_success = apply_changes_to_preview(content)
    return preview_success

def show_diff(content: str) -> None:
    """Show the changes as a diff with color output"""
    syntax = Syntax(content.strip(), "diff", theme="monokai", line_numbers=True)
    console.print(syntax)

def show_file_diff(original_file: str, modified_file: str) -> bool:
    """Show diff between two files using diff command. Returns True if differences found."""
    from rich.text import Text
    
    # Print the diff command
    console.print(f"Running command: diff -u {original_file} {modified_file}")
    
    # Run diff command with unified format
    result = subprocess.run(
        ['diff', '-u', original_file, modified_file],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 1:  # Files are different
        patch_content = result.stdout
        
        # Build rich text with proper coloring
        result_text = Text()
        for line in patch_content.split('\n'):
            if line.startswith('+++'):
                result_text.append(line + '\n', 'blue')
            elif line.startswith('---'):
                result_text.append(line + '\n', 'blue')
            elif line.startswith('+'):
                result_text.append(line + '\n', 'green')
            elif line.startswith('-'):
                result_text.append(line + '\n', 'red')
            elif line.startswith('@@'):
                result_text.append(line + '\n', 'cyan')
            else:
                result_text.append(line + '\n')
                
        console.print(result_text)
        return True
    elif result.returncode > 1:  # Error occurred
        console.print(f"[red]Error showing diff for {original_file}: {result.stderr}[/red]")
    
    console.print("[yellow]No differences found[/yellow]")
    return False