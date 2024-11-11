"""
TEST CMD: python -m codedriver.agent
"""

import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv

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
        # Claude-3 Sonnet context window is 200k tokens
        self.max_tokens_limit = 150000  # Leave buffer for response
        self.max_response_tokens = 4096  # Reasonable limit for code changes

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens (4 chars ~= 1 token)"""
        return len(text) // 4

    def send_message(self, prompt: str) -> Dict[Any, Any]:
        # Estimate tokens in prompt
        estimated_tokens = self._estimate_tokens(prompt)
        
        if estimated_tokens > self.max_tokens_limit:
            raise ValueError(
                f"Prompt too long (estimated {estimated_tokens} tokens). "
                f"Please reduce input size to stay within {self.max_tokens_limit} tokens."
            )

        data = {
            "model": "claude-3-sonnet-20240229",  # Updated to Sonnet model
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_response_tokens,
            "temperature": 0.3,  # Lower temperature for code changes
        }

        response = requests.post(
            f"{self.base_url}/messages", headers=self.headers, json=data
        )

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.text}")

        return response.json()

def main():
    claude = ClaudeAPI()
    test_prompt = "Hello, Claude! Can you summarize the purpose of this API?"
    try:
        response = claude.send_message(test_prompt)
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