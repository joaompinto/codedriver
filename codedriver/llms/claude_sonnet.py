"""Claude Sonnet API Integration"""

import os
import json
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import time
from functools import wraps
import random
from .base import BaseLLM
from rich import print as rprint
from .exceptions import LLMOverloadedError, LLMRateLimitError

console = Console()

class ClaudeSonnet(BaseLLM):
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        self.max_tokens_limit = 150000
        self.max_response_tokens = 4096
        self.logger = None  # Will be set by agent

    @property
    def name(self) -> str:
        return "Claude-3 Sonnet"

    # Claude API supported media types
    MEDIA_TYPES = {
        # Source code files
        ".py": "text/x-python",
        ".js": "application/javascript",
        ".ts": "text/plain",
        ".jsx": "application/javascript",
        ".tsx": "text/plain",
        ".java": "text/x-java",
        ".cpp": "text/x-c++src",
        ".h": "text/x-c++src",
        ".cs": "text/plain",
        ".go": "text/x-go",
        ".rb": "text/x-ruby",
        ".php": "text/x-php",
        ".rs": "text/x-rust",
        ".swift": "text/x-swift",
        ".kt": "text/x-kotlin",
        
        # Configuration and markup
        ".json": "application/json",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
        ".md": "text/markdown",
        ".html": "text/html",
        ".css": "text/css",
        ".xml": "text/xml",
        
        "": "text/plain"
    }

    def log_interaction(self, prompt: str, response: dict = None, error: Exception = None) -> None:
        """Log interaction with Claude API"""
        if not self.logger:
            return

        if error:
            self.logger.error(f"Claude API Error: {str(error)}\nPrompt: {prompt}")
        else:
            self.logger.info(f"Claude API Success\nPrompt: {prompt}\nResponse: {response}")

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _log_compression_info(self, response: requests.Response) -> None:
        encoding = response.headers.get('content-encoding', 'none')
        request_encoding = response.request.headers.get('accept-encoding', 'none')
        print(f"HTTP compression: request={request_encoding}, response={encoding}")

    def _get_media_type(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        return self.MEDIA_TYPES.get(ext, self.MEDIA_TYPES[""])

    def send_message(self, prompt: str, verbose: bool = False):
        estimated_tokens = self._estimate_tokens(prompt)
        
        if verbose:
            console.print("\n[blue]Claude AI Request:[/blue]")
            console.print(Panel(prompt, title="Prompt", border_style="blue"))
        
        if (estimated_tokens > self.max_tokens_limit):
            raise ValueError(
                f"Prompt too long (estimated {estimated_tokens} tokens). "
                f"Please reduce input size to stay within {self.max_tokens_limit} tokens."
            )

        messages = [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": prompt
            }]
        }]
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "messages": messages,
            "max_tokens": self.max_response_tokens
        }

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                json=data,
                timeout=30  # Add timeout
            )

            if response.status_code == 429:
                wait_time = int(response.headers.get('retry-after', '60'))
                raise LLMRateLimitError(
                    f"Claude API rate limit exceeded.",
                    wait_time=wait_time
                )
            elif response.status_code == 503:
                raise LLMOverloadedError("Claude API is currently overloaded.")
            elif response.status_code != 200:
                raise Exception(f"API request failed ({response.status_code}): {response.text}")
                
            response_data = response.json()
            
            self._log_compression_info(response)

            if verbose:
                console.print("\n[blue]Claude API Response:[/blue]")
                console.print(Panel(json.dumps(response_data, indent=2), title="Full Response", border_style="blue"))
                
            return response_data

        except Exception as e:
            raise
        except requests.exceptions.Timeout:
            raise LLMOverloadedError("Claude API request timed out.")
        except Exception as e:
            if isinstance(e, (LLMRateLimitError, LLMOverloadedError)):
                raise
            raise Exception(f"Claude API request failed: {str(e)}")
