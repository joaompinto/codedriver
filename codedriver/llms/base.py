"""Base LLM Interface"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
from ..utils.logging import log_api_interaction

class BaseLLM(ABC):
    logger: logging.Logger = None
    
    @abstractmethod
    def send_message(self, prompt: str, verbose: bool = False) -> Dict[Any, Any]:
        pass

    @abstractmethod
    def _get_media_type(self, filepath: str) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    def log_interaction(self, prompt: str, response: Dict[Any, Any] = None, error: Exception = None):
        """Log API interaction if logger is configured"""
        if self.logger:
            log_api_interaction(self.logger, self.name, prompt, response, error)