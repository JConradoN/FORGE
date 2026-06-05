"""
Decorador de logging para rastrear chamadas de função.
"""
import logging

# BUG-1: Callable não importado (from typing import Callable ausente)

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:  # NameError: Callable não definido
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        # BUG-2: msg.format(msg) — auto-referência; deveria ser func.__name__
        msg = "calling {}"
        LOG.debug(msg.format(msg))
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
