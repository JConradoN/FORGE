"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable  # Correção Bug-1: importar Callable

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:  # Correção Bug-2: usar func.__name__
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        msg = f"calling {func.__name__}"  # Correção Bug-2: usa nome da função
        LOG.debug(msg)
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
