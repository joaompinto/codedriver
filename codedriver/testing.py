import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from rich.console import Console
from rich.syntax import Syntax
import difflib
from pathlib import Path

console = Console()

def _copy(src: str, dst: str, is_dir: bool = False, silent: bool = False) -> None:
    """Helper function to perform copy operations"""
    if not silent:
        rel_src = os.path.relpath(src)
        rel_dst = os.path.relpath(dst)
        
        if os.path.exists(dst):
            console.print(f"[yellow]Replacing[/yellow] {rel_dst}")
        else:
            console.print(f"[green]Creating[/green] {rel_dst}")
        
    if is_dir:
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_patterns)
    else:
        shutil.copy2(src, dst)

def _ignore_patterns(path, names):
    """Helper function for ignoring .git directories"""
    return [n for n in names if n == '.git']

def _create_backup() -> str:
    """Create a backup of the working directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(tempfile.gettempdir(), f"codedriver_backup_{timestamp}")
    
    try:
        console.print("[blue]Creating backup...[/blue]")
        _copy(".", backup_dir, is_dir=True, silent=True)
        console.print(f"[dim]Backup created at: {backup_dir}[/dim]")
        return backup_dir
    except Exception as e:
        console.print(f"[red]Error creating backup:[/red] {str(e)}")
        return ""

def _process_changes(content: str, preview_dir: str) -> tuple[list, list]:
    """Process changes using full file content replacement"""
    test_cmds = []
    modified_files = []
    current_file = None
    current_content = []

    for line in content.strip().split("\n"):
        if line.startswith("### [") and line.endswith("]"):
            if current_file:
                # Create parent directories if needed
                filepath = os.path.join(preview_dir, current_file)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Write full file content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(current_content))
                modified_files.append(current_file)
                
                # Check for test commands
                for content_line in current_content:
                    if content_line.startswith('"""TEST CMD:'):
                        test_cmds.append(content_line.split(":", 1)[1].strip().strip('"""'))

            current_file = line[5:-1]
            current_content = []
        else:
            current_content.append(line)

    # Handle last file
    if current_file:
        filepath = os.path.join(preview_dir, current_file)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(current_content))
        modified_files.append(current_file)
        for content_line in current_content:
            if content_line.startswith('"""TEST CMD:'):
                test_cmds.append(content_line.split(":", 1)[1].strip().strip('"""'))

    return test_cmds, modified_files

def _setup_preview_dir() -> str:
    """Setup and return the preview directory path"""
    preview_dir = os.path.join(tempfile.gettempdir(), "codedriver_preview")
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

def _generate_patch_file(preview_dir: str, working_dir: str, modified_files: list) -> str:
    """Generate a unified patch file using the diff command"""
    patch_path = os.path.join(tempfile.gettempdir(), "changes.patch")
    
    try:
        with open(patch_path, 'w', encoding='utf-8') as patch_file:
            for file in modified_files:
                preview_path = os.path.join(preview_dir, file)
                working_path = os.path.join(working_dir, file)
                
                # If working file doesn't exist, create empty file for diff
                if not os.path.exists(working_path):
                    Path(working_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(working_path).touch()
                
                # Run diff command with unified format
                result = subprocess.run(
                    ['diff', '-u', working_path, preview_path],
                    capture_output=True,
                    text=True
                )
                
                # diff returns 1 if files are different, which is what we want
                if result.returncode == 1:
                    patch_file.write(result.stdout)
                    if not result.stdout.endswith('\n'):
                        patch_file.write('\n')
                elif result.returncode > 1:
                    # Any return code > 1 indicates an error
                    console.print(f"[red]Error generating diff for {file}:[/red] {result.stderr}")
                    return ''
                    
        # Return patch file path only if it contains changes
        if os.path.getsize(patch_path) > 0:
            return patch_path
            
        os.unlink(patch_path)
        return ''
        
    except Exception as e:
        console.print(f"[red]Error generating patch file:[/red] {str(e)}")
        if os.path.exists(patch_path):
            os.unlink(patch_path)
        return ''

def apply_changes_to_working(preview_dir: str, modified_files: list, backup_first: bool = True) -> bool:
    """Apply changes from preview directory to working directory using patch"""
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
            
        # Generate patch file
        patch_file = _generate_patch_file(preview_dir, ".", modified_files)
        if not patch_file:
            console.print("[yellow]No changes to apply[/yellow]")
            return True
            
        # Apply patch with -p0 to use exact paths
        console.print(f"\n[dim]Running: patch -p0 < {patch_file}[/dim]")
        result = subprocess.run(
            ['patch', '-p0', '--verbose'],
            input=open(patch_file, 'r').read(),
            shell=True,
            cwd=".",
            capture_output=True,
            text=True
        )
        
        try:
            os.unlink(patch_file)  # Clean up patch file
        except:
            pass
            
        if result.stdout:
            console.print("[dim]Patch output:[/dim]\n" + result.stdout)
        if result.stderr and result.returncode != 0:
            console.print("[red]Patch errors:[/red]\n" + result.stderr)
            return False
            
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

def show_directory_diff(original_dir: str, modified_dir: str) -> None:
    """Show diff between two directories using generated patch file"""
    from rich.text import Text
    
    # Get list of modified files
    modified_files = []
    for file in os.listdir(modified_dir):
        if os.path.isfile(os.path.join(modified_dir, file)):
            modified_files.append(file)
    
    # Generate patch file
    patch_file = _generate_patch_file(modified_dir, original_dir, modified_files)
    
    if not patch_file:
        console.print("[yellow]No differences found[/yellow]")
        return
        
    try:
        # Read and display patch content
        with open(patch_file, 'r', encoding='utf-8') as f:
            patch_content = f.read()
            
        # Build rich text with proper coloring
        result = Text()
        for line in patch_content.split('\n'):
            if line.startswith('+++'):
                result.append(line + '\n', 'blue')
            elif line.startswith('---'):
                result.append(line + '\n', 'blue')
            elif line.startswith('+'):
                result.append(line + '\n', 'green')
            elif line.startswith('-'):
                result.append(line + '\n', 'red')
            elif line.startswith('@@'):
                result.append(line + '\n', 'cyan')
            else:
                result.append(line + '\n')
                
        console.print(result)
        
    except Exception as e:
        console.print(f"[red]Error showing diff: {str(e)}[/red]")
    finally:
        try:
            os.unlink(patch_file)  # Clean up patch file
        except:
            pass