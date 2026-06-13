"""
Utilitário de retry com backoff linear.
"""
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def with_retry(func: Callable[[], T], max_attempts: int = 3, delay: float = 0.1) -> T:
    """
    Executa func até max_attempts vezes, com delay entre tentativas.
    Lança a última exceção se todas as tentativas falharem.
    """
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            # FIX BUG-3: condição era `attempt == 0` (relançava na primeira
            # falha, impedindo retentativas). Agora só relança na última
            # tentativa; nas demais, aguarda o delay e continua o loop.
            if attempt == max_attempts - 1:
                raise last_exc
            time.sleep(delay)

    raise last_exc  # type: ignore
