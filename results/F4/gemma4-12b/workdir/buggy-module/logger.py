"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        msg = "calling {}".format(func.__name__)
        LOG.debug(msg)
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
