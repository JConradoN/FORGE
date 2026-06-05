"""
Retry decorator with exponential back-off.
"""
import time


def retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    """Retry a function up to max_attempts times with exponential back-off."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay

            # FIX Bug 5: use < max_attempts (not max_attempts - 1) so all attempts are executed
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    # FIX Bug 6: raise immediately when attempts exhausted, sleep only if retrying
                    if attempt >= max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator


class RetryError(Exception):
    pass


def retry_call(func, args=(), kwargs={}, max_attempts=3, delay=0.0):
    """Call func retrying on any exception."""
    last_exc = None
    for i in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
    # FIX Bug 7: re-raise the original exception to preserve type and message
    raise last_exc
