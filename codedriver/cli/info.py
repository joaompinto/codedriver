from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
import json

from ..agent import LLMAgent  # Changed from ClaudeAPI
from ..scan import collect_files

console = Console()

def call_claude_with_progress(prompt: str, progress: Progress, message: str = "Waiting for response...", verbose: bool = False):
    """Utility function to call LLM Agent with progress indicator"""
    task = progress.add_task(message, total=None)
    agent = LLMAgent()  # Changed from ClaudeAPI
    response = agent.send_message(prompt, verbose=verbose)
    progress.update(task, visible=False)
    return response

def info_command(args=None):
    """Handle the info command logic"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Collect all file contents
        files_content, _, unhandled_files = collect_files(progress)

        if unhandled_files:
            console.print("\n[red]Error: Cannot proceed with unhandled files present[/red]")
            console.print("[yellow]Add these extensions to FILE_HANDLERS in scan.py to process them[/yellow]")
            return

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
            response = call_claude_with_progress(prompt, progress, "Analyzing project...", verbose=args.verbose)

            if "content" in response and len(response["content"]) > 0:
                print("\nProject Analysis:")
                markdown = Markdown(response["content"][0]["text"])
                console.print(markdown)
            else:
                print("Error: No content in response")
                print("Raw response:", json.dumps(response, indent=2))
        except Exception as e:
            print(f"Error getting analysis: {str(e)}")