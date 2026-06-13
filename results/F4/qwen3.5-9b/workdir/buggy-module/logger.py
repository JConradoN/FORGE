"""
Decorador de logging para rastrear chamadas de função.
"""
from typing import Callable  # FIX-4: importar Callable
import logging

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:  # FIX-5: agora Callable está definido
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        msg = f"calling {func.__name__}"  # FIX-6: usar func.__name__ em vez de msg.format(msg)
        LOG.debug(msg)
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
