import argparse
import difflib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm  # Add this import
from rich.syntax import Syntax

from .agent import Agent

console = Console()


class ClaudeAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",  # Fixed API version
        }

    def send_message(self, prompt: str) -> Dict[Any, Any]:
        data = {
            "model": "claude-3-sonnet-20240229",  # Updated to Sonnet model
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
        }

        response = requests.post(
            f"{self.base_url}/messages", headers=self.headers, json=data
        )

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.text}")

        return response.json()


def get_file_content(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"


def info(args=None):
    # Collect all file contents
    current_files = {}
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(
                (".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go")
            ):
                path = os.path.join(root, file)
                try:
                    current_files[path] = get_file_content(path)
                except Exception as e:
                    print(f"Warning: Could not read {path}: {e}")

    if not current_files:
        print("No code files found in the current directory.")
        return

    try:
        agent = Agent()
        response = agent.get_app_analysis(current_files, args.prompt if args else None)

        if response:
            print("\nProject Analysis:")
            markdown = Markdown(response)
            console.print(markdown)
        else:
            print("Error: No content in response")

    except Exception as e:
        print(f"Error getting analysis: {str(e)}")


def generate_diff(original_path: str, new_path: str) -> str:
    """Generate a unified diff between two files with syntax highlighting"""
    try:
        with open(original_path, "r") as f:
            original_lines = f.readlines()
    except FileNotFoundError:
        original_lines = []

    with open(new_path, "r") as f:
        new_lines = f.readlines()

    diff_lines = list(
        difflib.unified_diff(
            original_lines, new_lines, fromfile=original_path, tofile=new_path
        )
    )

    if not diff_lines:
        return "No changes"

    # Determine language for syntax highlighting
    diff_text = "".join(diff_lines)

    # Create syntax highlighted diff
    syntax = Syntax(diff_text, "diff", theme="monokai")
    return syntax


def has_actual_changes(file_path: str, temp_file: str) -> bool:
    """Check if there are actual changes between files"""
    if not os.path.exists(file_path):
        return True  # New file counts as a change

    with open(file_path, "r") as f:
        original = f.read()
    with open(temp_file, "r") as f:
        new = f.read()
    return original != new


def _write_temp_files(file_changes: dict, temp_dir: str) -> dict:
    """Write changes to temporary files and return mapping of paths to temp files."""
    temp_files = {}
    for file_path, content in file_changes.items():
        if not file_path or not content:
            continue

        abs_path = os.path.abspath(file_path)
        temp_file = os.path.join(temp_dir, os.path.basename(file_path))
        os.makedirs(os.path.dirname(temp_file), exist_ok=True)

        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)
        temp_files[abs_path] = temp_file

    return temp_files


def _check_for_changes(temp_files: dict) -> bool:
    """Check if any files have actual changes."""
    for file_path, temp_file in temp_files.items():
        if has_actual_changes(file_path, temp_file):
            return True
    return False


def _display_changes(temp_files: dict) -> None:
    """Display all file changes with syntax highlighting."""
    for file_path, temp_file in temp_files.items():
        if has_actual_changes(file_path, temp_file):
            print(f"\nDiff for {file_path}:")
            if os.path.exists(file_path):
                diff = generate_diff(file_path, temp_file)
                console.print(diff)
            else:
                print("(New file)")
                with open(temp_file, "r") as f:
                    ext = os.path.splitext(file_path)[1].lstrip(".") or "text"
                    syntax = Syntax(f.read(), ext, theme="monokai")
                    console.print(syntax)


def _apply_confirmed_changes(temp_files: dict) -> bool:
    """Apply changes after confirmation."""
    try:
        for file_path, temp_file in temp_files.items():
            if has_actual_changes(file_path, temp_file):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                shutil.copy2(temp_file, file_path)
        return True
    except Exception as e:
        print(f"Failed to apply changes: {str(e)}")
        return False


def apply_changes(file_changes: dict) -> bool:
    """Apply the changes to the files with diff preview."""
    if not file_changes:
        print("No changes to apply")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_files = _write_temp_files(file_changes, temp_dir)

        if not temp_files:
            print("No valid files to modify")
            return False

        print("\nAnalyzing changes...")
        if not _check_for_changes(temp_files):
            print("No changes detected in any files")
            return False

        print("\nProposed changes:")
        _display_changes(temp_files)

        if Confirm.ask("\nDo you want to apply these changes?"):
            return _apply_confirmed_changes(temp_files)

        return False


def _read_single_file(file_path: Path, base_path: Path) -> tuple[str, str]:
    """Read a single file and return its path and content."""
    if not file_path.is_absolute():
        file_path = base_path / file_path

    try:
        return str(file_path.resolve()), file_path.read_text()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return None, None


def _read_specified_files(file_list: list[str], base_path: Path) -> Dict[str, str]:
    """Read content of specified files."""
    files = {}
    for filepath in file_list:
        path, content = _read_single_file(Path(filepath), base_path)
        if path and content:
            files[path] = content
        else:
            print(f"Warning: File not found: {filepath}")
    return files


def _scan_directory(path: Path) -> Dict[str, str]:
    """Scan directory for code files."""
    files = {}
    code_extensions = [".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go"]

    for filepath in path.rglob("*"):
        if filepath.is_file() and filepath.suffix in code_extensions:
            path, content = _read_single_file(filepath, path)
            if path and content:
                files[path] = content

    return files


def process_change_command(args):
    """Process the change command"""
    if not args.prompt:
        print("Error: Change prompt is required")
        return 1

    path = Path(args.path).resolve() if args.path else Path.cwd()
    if not path.exists():
        print(f"Error: Path {path} does not exist")
        return 1

    try:
        # Read files based on command arguments
        current_files = (
            _read_specified_files(args.files.split(), path)
            if args.files
            else _scan_directory(path)
        )

        if not current_files:
            print("No valid files to process")
            return 1

        # Get and apply modifications
        agent = Agent()
        result = agent.get_app_changes(args.prompt, current_files)

        if not result or "files" not in result:
            print("Error: Invalid response from AI")
            return 1

        if apply_changes(result["files"]):
            print("\nChanges applied successfully!")
            if result.get("messageSize"):
                print(f"\n{result['messageSize']}")
        else:
            print("\nNo changes were applied.")

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

    return 0


def main():
    """Main entry point"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is required")
        print("Please set it with: export ANTHROPIC_API_KEY=your_api_key")
        return 1

    parser = argparse.ArgumentParser(
        description="CodeDriver - AI-powered code modification tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    info_parser = subparsers.add_parser(
        "info", help="Analyze code in current directory"
    )
    info_parser.add_argument(
        "prompt", nargs="?", help="Optional question about the code"
    )

    # Change command
    change_parser = subparsers.add_parser("change", help="Change code based on prompt")
    change_parser.add_argument("prompt", help="Change description")
    change_parser.add_argument("--path", help="Path to project directory")
    change_parser.add_argument(
        "--files",
        help="Space-separated list of files to process (e.g., 'file1.py file2.js')",
    )

    args = parser.parse_args()

    if args.command == "info":
        return info(args)
    elif args.command == "change":
        return process_change_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
