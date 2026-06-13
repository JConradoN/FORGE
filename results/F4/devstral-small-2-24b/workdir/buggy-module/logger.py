"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable  # Correção BUG-1: import missing

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        # Correção BUG-2: usa func.__name__ ao invés de auto-referência
        LOG.debug("calling %s", func.__name__)
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
