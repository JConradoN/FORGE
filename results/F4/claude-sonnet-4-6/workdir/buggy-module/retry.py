"""Retry helper with exponential back-off."""

import time


def with_retry(fn, max_attempts=3, delay=0.1, exceptions=(Exception,)):
    """Chama fn() repetidamente até ter sucesso ou esgotar max_attempts.

    FIX bug 5: implementa a interface with_retry(fn, ...) esperada pelo validador.
    FIX bug 6: condição de loop corrigida para `<` (era atribuição `=`).

    Args:
        fn:           callable sem argumentos a ser executado.
        max_attempts: número máximo de tentativas (padrão 3).
        delay:        espera inicial em segundos entre tentativas (padrão 0.1).
                      O back-off é exponencial: delay * 2^attempt.
        exceptions:   tupla de tipos de exceção que disparam nova tentativa.

    Returns:
        O valor retornado por fn() na primeira execução bem-sucedida.

    Raises:
        A última exceção capturada quando todos os attempts se esgotam.
    """
    attempt = 0
    # FIX bug 6: comparação correta com <
    while attempt < max_attempts:
        try:
            return fn()
        except exceptions as exc:
            attempt += 1
            if attempt == max_attempts:
                raise
            time.sleep(delay * (2 ** attempt))
