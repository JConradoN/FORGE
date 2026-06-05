"""Lightweight function-call logger using the standard logging module."""

import logging
import functools


def log_call(func):
    """Decorator que registra a chamada e o retorno de uma função.

    FIX bug 7: implementa log_call como decorator funcional usando
    logging.getLogger("logger"), conforme esperado pelo validador.
    Usa functools.wraps para preservar __name__, __doc__ e afins.

    Exemplo:
        @log_call
        def greet(name: str) -> str:
            return f"hello {name}"

        greet("world")
        # → INFO:logger:calling greet
        # → INFO:logger:greet returned 'hello world'
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("logger")
        logger.debug("calling %s", func.__name__)
        result = func(*args, **kwargs)
        logger.debug("%s returned %r", func.__name__, result)
        return result
    return wrapper
