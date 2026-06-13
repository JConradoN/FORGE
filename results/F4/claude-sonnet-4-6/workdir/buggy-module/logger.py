"""
Decorador de logging para rastrear chamadas de função.
"""
import logging
from typing import Callable  # FIX BUG-4: import ausente que causava NameError

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        # FIX BUG-5: msg.format(msg) usava auto-referência ("calling calling {}");
        # corrigido para func.__name__ que registra o nome real da função.
        msg = "calling {}"
        LOG.debug(msg.format(func.__name__))
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper
