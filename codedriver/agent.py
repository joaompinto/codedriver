import logging
import os
from typing import Dict

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self.anthropic = Anthropic(api_key=self.api_key)
        self.debug = os.environ.get("DEBUG") == "1"

    def get_app_changes(
        self, prompt: str, current_files: Dict[str, str] = None
    ) -> Dict[str, any]:
        """Get changed files from AI for the app."""
        try:
            system_prompt = (
                "You are an expert developer. You will modify or create code files based on the user's request.\n"
                "IMPORTANT: Your response must follow this exact format:\n\n"
                "BEGIN_RESPONSE\n"
                "file: filename.ext\n"
                "<code content>\n"
                "END_FILE\n"
                "END_RESPONSE\n"
            )

            file_content = ""
            if current_files:
                file_content = "Current files:\n\n"
                for fname, content in current_files.items():
                    file_content += f"file: {fname}\n{content}\n---\n"

            user_prompt = (
                f"{file_content}\n"
                f"Request: {prompt}\n\n"
                "Provide the complete modified or new files following the specified format."
            )

            response = self._get_ai_response(prompt, user_prompt, system_prompt)

            # Parse and validate response
            files = self.parse_response(response)
            if not files:
                logger.error(f"Invalid AI response format: {response}")
                raise ValueError("Invalid AI response format")

            return {
                "files": files,
                "messageSize": None,  # Can add message size handling if needed
            }

        except Exception as e:
            logger.error(f"Error getting Claude instructions: {e}", exc_info=True)
            raise

    def get_app_analysis(
        self, files_content: Dict[str, str], question: str = None
    ) -> str:
        """Get analysis of code files from AI."""
        try:
            system_prompt = (
                "You are an expert developer analyzing code. "
                "Provide clear, concise analysis focusing on the main aspects of the codebase."
            )

            file_content = "Files to analyze:\n\n"
            for fname, content in files_content.items():
                file_content += f"file: {fname}\n{content}\n---\n"

            if question:
                user_prompt = f"Please analyze these code files and answer this specific question: {question}"
                "\n\n{file_content}"
            else:
                base_prompt = """Please analyze these code files and provide a concise summary of:
1. The main purpose of the application
2. Key features and functionality
3. Main components and their roles"""
                user_prompt = f"{base_prompt}\n\n{file_content}"

            response = self._get_ai_response(
                "Analysis request", user_prompt, system_prompt
            )
            return response

        except Exception as e:
            logger.error(f"Error getting analysis: {e}", exc_info=True)
            raise

    def _process_file_content(
        self, lines: list, start_idx: int
    ) -> tuple[str, list[str], int]:
        """Process file content from a specific line index."""
        current_file = None
        current_content = []
        idx = start_idx

        while idx < len(lines):
            line = lines[idx].rstrip()

            if (
                line == "END_RESPONSE"
                or line.startswith("file: ")
                or line == "END_FILE"
            ):
                break

            current_content.append(line)
            idx += 1

        return current_file, current_content, idx

    def _save_file_content(self, files: dict, current_file: str, content: list) -> None:
        """Save file content to files dictionary if valid."""
        if current_file and content:
            files[current_file] = "\n".join(content)

    def parse_response(self, response: str) -> Dict[str, str]:
        """Parse AI response into a dictionary of files."""
        files = {}
        lines = response.split("\n")
        current_file = None
        current_content = []

        try:
            start_idx = lines.index("BEGIN_RESPONSE") + 1
        except ValueError:
            return {}

        idx = start_idx
        while idx < len(lines):
            line = lines[idx].rstrip()

            if line == "END_RESPONSE":
                self._save_file_content(files, current_file, current_content)
                break

            if line.startswith("file: "):
                self._save_file_content(files, current_file, current_content)
                current_file = line[6:].strip()
                current_content = []
                idx += 1
                continue

            if line == "END_FILE":
                self._save_file_content(files, current_file, current_content)
                current_file = None
                current_content = []
                idx += 1
                continue

            if current_file is not None:
                _, new_content, new_idx = self._process_file_content(lines, idx)
                current_content.extend(new_content)
                idx = new_idx
            else:
                idx += 1

        return files

    def _get_ai_response(self, prompt: str, content: str, system: str) -> str:
        """Get response from AI model."""
        try:
            response = self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0,
                system=system,
                messages=[{"role": "user", "content": content}],
            )

            if not response.content or not response.content[0].text:
                raise ValueError("Empty response from AI")

            return response.content[0].text

        except Exception as e:
            logger.error(f"AI request failed: {str(e)}")
            raise
