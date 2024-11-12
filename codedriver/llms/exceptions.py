"""Custom exceptions for LLM handling"""

class LLMBaseError(Exception):
    def __init__(self, message: str, wait_time: int = None):
        self.message = message
        self.wait_time = wait_time
        super().__init__(message)

class LLMRateLimitError(LLMBaseError):
    """Raised when API rate limit is exceeded"""
    pass

class LLMOverloadedError(LLMBaseError):
    """Raised when API service is overloaded"""
    pass

class LLMQuotaExceededError(LLMBaseError):
    """Raised when API quota is exceeded"""
    pass