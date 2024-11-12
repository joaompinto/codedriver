"""Google Gemini Pro API Integration"""

import os
import json
from typing import Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import time
from functools import wraps
import random
from .base import BaseLLM
from .exceptions import LLMRateLimitError, LLMQuotaExceededError  # Add this import

console = Console()

def retry_with_backoff(max_retries=3, initial_delay=1, max_delay=16):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if retries == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
                    retries += 1
        return wrapper
    return decorator

class GeminiPro(BaseLLM):
    @property
    def name(self) -> str:
        return "Gemini Pro"

    # Supported media types (subset of Claude's, matching Gemini's capabilities)
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
        
        # Configuration and markup
        ".json": "application/json",
        ".yaml": "text/plain",
        ".yml": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".css": "text/css",
        
        "": "text/plain"
    }

    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Gemini Pro context window is 30k tokens
        self.max_tokens_limit = 25000  # Leave buffer for response
        self.max_response_tokens = 2048
        self.logger = None  # Will be set by agent

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens (4 chars ~= 1 token)"""
        return len(text) // 4

    def _get_media_type(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        return self.MEDIA_TYPES.get(ext, self.MEDIA_TYPES[""])

    @retry_with_backoff()
    def send_message(self, prompt: str, verbose: bool = False) -> Dict[Any, Any]:
        estimated_tokens = self._estimate_tokens(prompt)
        
        if verbose:
            console.print("\n[blue]Gemini AI Request:[/blue]")
            console.print(Panel(prompt, title="Prompt", border_style="blue"))
        
        if (estimated_tokens > self.max_tokens_limit):
            raise ValueError(
                f"Prompt too long (estimated {estimated_tokens} tokens). "
                f"Please reduce input size to stay within {self.max_tokens_limit} tokens."
            )

        generation_config = genai.types.GenerationConfig(
            max_output_tokens=self.max_response_tokens,
        )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            if not response.text:
                raise Exception("Empty response from Gemini API")

            # Convert Gemini response to Claude-compatible format
            response_data = {
                "content": [{
                    "type": "text",
                    "text": response.text
                }]
            }
            
            if verbose:
                console.print("\n[blue]Gemini API Response:[/blue]")
                console.print(Panel(json.dumps(response_data, indent=2), title="Full Response", border_style="blue"))
                
            return response_data

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg:
                raise LLMRateLimitError(
                    "overloaded_error: Gemini API rate limit or quota exceeded. "
                    "Try switching to another LLM."
                )
            raise Exception(f"Gemini API request failed: {str(e)}")

    def log_interaction(self, prompt: str, response: Dict[Any, Any] = None, error: Exception = None) -> None:
        """Log interaction with Gemini API"""
        if not self.logger:
            return

        if error:
            self.logger.error(f"Gemini API Error: {str(error)}\nPrompt: {prompt}")
        else:
            self.logger.info(f"Gemini API Success\nPrompt: {prompt}\nResponse: {response}")
