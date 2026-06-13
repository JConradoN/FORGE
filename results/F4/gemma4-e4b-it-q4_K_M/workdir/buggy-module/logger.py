"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable # CORREÇÃO BUG-1: Importação adicionada

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        # CORREÇÃO BUG-2: Usa func.__name__ para obter o nome correto da função.
        msg = f"calling {func.__name__}"
        LOG.debug(msg)
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
