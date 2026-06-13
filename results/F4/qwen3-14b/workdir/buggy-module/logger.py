from typing import Callable

import logging

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:  # NameError: Callable não definido
    """Decorator que loga entrada e saída de uma função."""
    def wrapper(*args, **kwargs):
        # BUG: msg.format(msg) — auto-referência; deveria ser func.__name__
        msg = "calling {}"
        LOG.debug(msg.format(func.__name__))
        result = func(*args, **kwargs)
        LOG.debug("done")
        return result
    return wrapper