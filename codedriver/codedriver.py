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

    # Clean up the patch content
    lines = content.strip().split("\n")
    cleaned_lines = []
    for line in lines:
        if line.startswith(("---", "+++")) and not line.startswith(
            ("--- ./", "+++ ./")
        ):
            # Add ./ to relative paths if missing
            parts = line.split(" ")
            if len(parts) > 1:
                cleaned_lines.append(f"{parts[0]} ./{parts[1]}")
            continue
        cleaned_lines.append(line)

    cleaned_content = "\n".join(cleaned_lines)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tmp:
        tmp.write(cleaned_content)
        tmp.flush()
        tmp_path = tmp.name

    try:
        # First try with -p0
        result = subprocess.run(
            ["patch", "-p0", "--forward", "--verbose"],
            stdin=open(tmp_path, "r"),
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # If p0 fails, try with -p1
            result = subprocess.run(
                ["patch", "-p1", "--forward", "--verbose"],
                stdin=open(tmp_path, "r"),
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                check=False,
            )

        # Print debug information
        print("\nPatch attempt output:")
        if result.stdout:
            print("stdout:", result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)

        os.unlink(tmp_path)
        return result.returncode == 0

    except Exception as e:
        print(f"Failed to apply changes: {str(e)}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
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

Format your response as a unified diff file with these requirements:
1. Start each file diff with "--- filename" and "+++ filename"
2. Use relative paths from the current directory
3. Include @@ line numbers @@
4. Only output the diff content, no other text

Example format:
--- ./path/to/file.py
+++ ./path/to/file.py
@@ -1,3 +1,3 @@
 line
-old line
+new line
 line
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
