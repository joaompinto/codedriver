"""Logging utilities for CodeDriver"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

def setup_api_logging(filename: str = None) -> logging.Logger:
    """Setup logging for API interactions
    
    Args:
        filename: Optional custom log filename. If not provided, uses date-based name.
    """
    # Create logs directory
    log_dir = Path.home() / ".codedriver" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log file with custom name or default timestamp
    if filename:
        log_file = log_dir / filename
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"api_{today}.log"
    
    # Configure logger
    logger = logging.getLogger("codedriver.api")
    logger.setLevel(logging.DEBUG)
    
    # File handler with text formatting instead of JSON
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def log_api_interaction(
    logger: logging.Logger,
    llm_name: str,
    prompt: str,
    response: Dict[Any, Any],
    error: Exception = None
) -> None:
    """Log an API interaction in plain text format"""
    # Format multiline prompt for readability
    prompt_formatted = prompt.replace('\n', '\n\t')
    
    if error:
        message = f"""
LLM: {llm_name}
ERROR: {str(error)}
PROMPT:
\t{prompt_formatted}
"""
    else:
        # Extract text content from response if available
        response_text = response.get("content", [{}])[0].get("text", str(response)) if response else "No response"
        response_formatted = response_text.replace('\n', '\n\t')
        
        message = f"""
LLM: {llm_name}
PROMPT:
\t{prompt_formatted}
RESPONSE:
\t{response_formatted}
"""
    
    logger.info(message.strip())