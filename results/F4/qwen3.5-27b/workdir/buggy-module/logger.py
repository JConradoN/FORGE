"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable  # Correção Bug-4: adiciona import faltante

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        msg = "calling {}"
        # Correção Bug-5: usa func.__name__ ao invés de auto-referência
        LOG.debug(msg.format(func.__name__))
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
