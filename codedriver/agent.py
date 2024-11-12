"""
TEST CMD: python -m codedriver.agent
"""

from typing import Any, Dict, List
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from .llms.claude_sonnet import ClaudeSonnet
from .llms.google_gemini import GeminiPro
from .llms.registry import LLMRegistry
from .llms.exceptions import LLMOverloadedError, LLMRateLimitError, LLMQuotaExceededError
from .utils.logging import setup_api_logging
import datetime
import dateutil.parser
from datetime import datetime  # Add this import
import tempfile  # Add this import
import os  # Add this import
import uuid  # Add this import
import re  # Add this import at the top with other imports
import hashlib  # Add this import
import base64  # Add this import

console = Console()

class LLMAgent:
    """AI Agent for managing multiple LLMs and processing code changes"""
    
    def __init__(self):
        # Generate unique instance ID
        self.instance_id = str(uuid.uuid4())[:8]
        
        # Initialize LLMs first
        self.llms = [ClaudeSonnet(), GeminiPro()]
        
        # Setup logging with instance-specific filename
        logger = setup_api_logging(filename=f"agent_{self.instance_id}.log")
        
        # Configure logger for each LLM
        for llm in self.llms:
            llm.logger = logger

        self.registry = LLMRegistry()
        current_llm = self.registry.get_current_llm()
        
        # Set default to first LLM if none selected
        if not current_llm:
            self.current_llm_index = 0
            self.registry.record_switch("none", self.llms[0].name)
        else:
            # Use selected LLM
            for i, llm in enumerate(self.llms):
                if llm.name == current_llm:
                    self.current_llm_index = i
                    break
        
        self.file_stats = {}
        self.files_to_process = {}

    def _get_alternative_llm_names(self) -> List[str]:
        """Get names of alternative LLMs"""
        current = self.llms[self.current_llm_index].name
        return [llm.name for llm in self.llms if llm.name != current]

    def _format_wait_time(self, seconds: int) -> str:
        """Format wait time in a human readable way"""
        if seconds < 60:
            return f"{seconds} seconds"
        mins = seconds // 60
        if mins < 60:
            return f"{mins} minutes"
        return f"{mins // 60} hours and {mins % 60} minutes"

    def _get_llm_status(self, llm_name: str) -> str:
        """Get current status of an LLM including rate limit info"""
        limit_info = self.registry.get_rate_limit_info(llm_name)
        if limit_info:
            available_at = dateutil.parser.parse(limit_info["until"])
            wait_time = (available_at - datetime.utcnow()).total_seconds()
            if wait_time > 0:
                return f"Rate limited for {self._format_wait_time(int(wait_time))}"
        return "Available"

    def _send_message(self, prompt: str, verbose: bool = False) -> Dict[Any, Any]:
        try:
            # Check if current LLM is rate limited
            current_llm = self.llms[self.current_llm_index]
            limit_info = self.registry.get_rate_limit_info(current_llm.name)
            if limit_info:
                available_at = dateutil.parser.parse(limit_info["until"])
                wait_time = (available_at - datetime.utcnow()).total_seconds()
                if wait_time > 0:
                    raise LLMRateLimitError(
                        "LLM is rate limited",
                        wait_time=int(wait_time)
                    )

            response = current_llm.send_message(prompt, verbose)  
            current_llm.log_interaction(prompt, response)
            return response

        except LLMRateLimitError as e:
            # Record rate limit in registry
            self.registry.record_rate_limit(current_llm.name, e.wait_time)
            current_llm.log_interaction(prompt, error=e)
            
            # Show status of all LLMs
            alternatives = self._get_alternative_llm_names()
            llm_statuses = [
                f"  - {llm.name}: {self._get_llm_status(llm.name)}"
                for llm in self.llms
            ]
            
            suggestion = "\n".join([
                f"[red]Rate limit exceeded for {current_llm.name}.[/red]",
                "\n[yellow]Current LLM Status:[/yellow]",
                *llm_statuses,
                "\n[yellow]Available commands:[/yellow]",
                *[f"  codedriver set-llm '{name}'" for name in alternatives 
                  if not self.registry.get_rate_limit_info(name)]
            ])
            console.print(suggestion)
            
            # Suggest changing to an available LLM
            available_llms = [name for name in alternatives if not self.registry.get_rate_limit_info(name)]
            if available_llms:
                console.print(f"\n[yellow]Suggested action:[/yellow] Switch to an available LLM using one of these commands:")
                for name in available_llms:
                    console.print(f"  codedriver set-llm '{name}'")
            raise

        except LLMOverloadedError as e:
            self.llms[self.current_llm_index].log_interaction(prompt, error=e)
            alternatives = self._get_alternative_llm_names()
            suggestion = "\n".join([
                f"[red]{self.llms[self.current_llm_index].name} is currently overloaded.[/red]",
                "[yellow]Recommended actions:[/yellow]",
                "  1. Try again in a few minutes",
                "  2. Switch to another LLM using one of these commands:",
                *[f"     codedriver set-llm '{name}'" for name in alternatives]
            ])
            console.print(suggestion)
            raise

        except LLMQuotaExceededError as e:
            self.llms[self.current_llm_index].log_interaction(prompt, error=e)
            alternatives = self._get_alternative_llm_names()
            suggestion = "\n".join([
                f"[red]API quota exceeded for {self.llms[self.current_llm_index].name}.[/red]",
                "[yellow]Options:[/yellow]",
                "  1. Wait for quota reset (usually daily)",
                "  2. Switch to another LLM using one of these commands:",
                *[f"     codedriver set-llm '{name}'" for name in alternatives]
            ])
            console.print(suggestion)
            raise

        except Exception as e:
            self.llms[self.current_llm_index].log_interaction(prompt, error=e)
            raise

    def send_message(self, prompt: str, verbose: bool = False) -> Dict[Any, Any]:
        return self._send_message(prompt, verbose)

    def clear_stats(self):
        self.file_stats = {}

    def track_file(self, filename: str, content: str):
        self.file_stats[filename] = len(content.split('\n'))

    def get_file_stats(self):
        return self.file_stats

    def _read_file_content(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading {filepath}: {str(e)}"

    def set_files_to_process(self, files: list[str]) -> None:
        self.files_to_process = files
        self.file_stats = {}

    def _normalize_path(self, filepath: str) -> str:
        return str(Path(filepath)).lstrip('./')

    def _generate_delimiter(self) -> str:
        """Generate a unique delimiter with random component"""
        random_part = base64.urlsafe_b64encode(os.urandom(6)).decode('ascii')
        return f"@==CODEDRIVER=={random_part}==@"

    def _hash_content(self, content: str) -> str:
        """Generate short hash of content for validation"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]

    def _display_raw_response(self, content: str, verbose: bool = False) -> None:
        """Display raw LLM response in a readable format"""
        if verbose:
            console.print("\n[blue]Raw Response:[/blue]")
            console.print(Panel(content, border_style="blue"))

    def _parse_file_changes(self, content: str, start_delimiter: str, end_delimiter: str) -> list:
        """Parse file changes from LLM response"""
        changes = []
        file_pattern = (
            re.escape(start_delimiter) + 
            r"\s*FILE\s+(MODIFY|CREATE|DELETE)\s+([^\s]+)\s+([a-f0-9]{8})\s*\n(.*?)\n\s*" +
            re.escape(end_delimiter) + r"\s*FILE"
        )
        
        for match in re.finditer(file_pattern, content, re.DOTALL):
            changes.append({
                'operation': match.group(1).lower(),
                'filepath': match.group(2).strip(),
                'hash': match.group(3),
                'content': match.group(4).strip()
            })
        return changes

    def process_changes(self, change_request: str, verbose: bool = False) -> Dict[Any, Any]:
        files_content = []
        for filepath in self.files_to_process:
            content = self._read_file_content(filepath)
            self.track_file(filepath, content)
            media_type = self.llms[self.current_llm_index]._get_media_type(filepath)
            files_content.append(f"File: {filepath}\nType: {media_type}\n\n{content}\n")

        # Show files that will be processed
        console.print("\n[blue]Processing files:[/blue]")
        for filepath in self.files_to_process:
            console.print(f"  📄 {filepath}")

        # Generate unique delimiters for this session
        start_delimiter = self._generate_delimiter()
        end_delimiter = self._generate_delimiter()

        prompt = f"""I need help modifying some code files. Here are the current files:

{chr(10).join(files_content)}

The requested changes are:
{change_request}

Use these EXACT markers to format your response (note: these are unique for this session):

{start_delimiter} SUMMARY
Brief description of changes
{end_delimiter} SUMMARY

For each file change, use this format:
{start_delimiter} FILE <operation> <filepath> <hash>
File content goes here
{end_delimiter} FILE

Where:
- <operation> is: MODIFY, CREATE, or DELETE
- <filepath> is the path without './' prefix
- <hash> will be provided by you as content verification
- For DELETE operations, no content is needed

Example:
{start_delimiter} FILE MODIFY src/main.py abc123
def main():
    print("hello")
{end_delimiter} FILE
"""

        # Create preview directory and process response
        preview_dir = tempfile.mkdtemp(prefix="codedriver_preview_")
        console.print(f"\n[blue]Preview Directory:[/blue] Changes are staged in: [cyan]{preview_dir}[/cyan]")

        response = self._send_message(prompt, verbose)

        if "content" in response and len(response["content"]) > 0:
            try:
                content = response["content"][0]["text"]
                
                # Display raw response if requested
                self._display_raw_response(content, verbose)

                # Process file changes
                changes = self._parse_file_changes(content, start_delimiter, end_delimiter)
                
                # Display changes overview
                if changes:
                    console.print("\n[blue]Changes Overview:[/blue]")
                    for change in changes:
                        op_color = {
                            'create': 'green',
                            'modify': 'yellow',
                            'delete': 'red'
                        }.get(change['operation'], 'white')
                        
                        op_text = change['operation'].title()
                        console.print(f"[{op_color}]{op_text}:[/] {change['filepath']}")
                else:
                    console.print("\n[yellow]No file changes detected in response[/yellow]")

                # Continue with existing processing
                modified_files = []
                for change in changes:
                    operation = change['operation']
                    filepath = change['filepath']
                    provided_hash = change['hash']
                    content = change['content'] if operation != "delete" else ""

                    # Verify content hash if content exists
                    if content and self._hash_content(content) != provided_hash:
                        console.print(f"[red]Warning: Content verification failed for {filepath}[/red]")
                        continue

                    # Process the file change
                    if operation == "delete":
                        if os.path.exists(filepath):
                            modified_files.append((filepath, operation))
                            console.print(f"[red]Will delete:[/red] {filepath}")
                    else:
                        if content:
                            preview_path = os.path.join(preview_dir, filepath)
                            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
                            
                            with open(preview_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            
                            modified_files.append((filepath, operation))
                            console.print(f"[{'green' if operation == 'create' else 'yellow'}]{operation.title()}:[/] {filepath}")

                response["modified_files"] = modified_files

            except Exception as e:
                console.print(f"[red]Error processing changes:[/red] {str(e)}")
                if verbose:
                    console.print("\n[yellow]Raw response content:[/yellow]")
                    console.print(response["content"][0]["text"])
                raise

        return response

def main():
    """Test the LLM Agent functionality"""
    agent = LLMAgent()
    test_prompt = "Hello! Can you summarize the purpose of this API?"
    try:
        response = agent.send_message(test_prompt)
        if "content" in response and len(response["content"]) > 0:
            print("API Test Successful!")
            print("Response:", response["content"][0]["text"])
        else:
            print("Error: No content in response")
            print("Raw response:", json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error during API test: {str(e)}")

if __name__ == "__main__":
    main()