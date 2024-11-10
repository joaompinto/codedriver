import argparse
import json
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Confirm  # Add this import

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


def info(args=None):  # Accept an optional argument
    # Collect all file contents
    files_content = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(
                (".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go")
            ):
                path = os.path.join(root, file)
                content = get_file_content(path)
                files_content.append(f"File: {path}\n\n{content}\n")

    if not files_content:
        print("No code files found in the current directory.")
        return

    # Prepare prompt for Claude
    prompt = """Please analyze these code files and provide a concise summary of:
1. The main purpose of the application
2. Key features and functionality
3. Main components and their roles

Here are the files:

{}""".format(
        "\n---\n".join(files_content)
    )

    try:
        claude = ClaudeAPI()
        response = claude.send_message(prompt)

        if "content" in response and len(response["content"]) > 0:
            print("\nProject Analysis:")
            markdown = Markdown(response["content"][0]["text"])
            console.print(markdown)
        else:
            print("Error: No content in response")
            print("Raw response:", json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error getting analysis: {str(e)}")


def apply_changes(content: str):
    """Apply the changes to the current directory"""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch") as tmp:
        tmp.write(content)
        tmp.flush()

        try:
            result = subprocess.run(
                ["patch", "-p1", "--forward"],
                stdin=open(tmp.name),
                cwd=os.getcwd(),  # Explicitly set working directory
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception, handle output manually
            )

            if result.returncode == 0:
                if result.stderr:
                    print("Patch output:", result.stderr)
                return True
            else:
                print("Patch failed:", result.stderr)
                return False

        except Exception as e:
            print(f"Failed to apply changes: {str(e)}")
            return False


def change(text: str):  # Renamed from changes to change
    files_content = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(
                (".py", ".js", ".ts", ".java", ".cpp", ".h", ".cs", ".go")
            ):
                path = os.path.join(root, file)
                content = get_file_content(path)
                files_content.append(f"File: {path}\n\n{content}\n")

    if not files_content:
        print("No code files found in the current directory.")
        return

    prompt = """I need help modifying some code files. Here are the current files:

{}

The requested changes are:
{}

Format your response as as an unified diff file with file content changes.
Do not response any other text, just the diff.
""".format(
        "\n---\n".join(files_content), text
    )

    try:
        claude = ClaudeAPI()
        response = claude.send_message(prompt)

        if "content" in response and len(response["content"]) > 0:
            changes_content = response["content"][0]["text"]
            print("\nSuggested Changes:")
            console.print(changes_content)

            if Confirm.ask("\nDo you want to apply these changes?"):
                if apply_changes(changes_content):
                    print("Changes applied successfully!")
                else:
                    print(
                        "Failed to apply changes. You may need to apply them manually."
                    )
        else:
            print("Error: No content in response")
            print("Raw response:", json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error getting changes: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="CodeDriver CLI")
    subparsers = parser.add_subparsers(dest="command")

    parser_info = subparsers.add_parser("info", help="Display info")
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
