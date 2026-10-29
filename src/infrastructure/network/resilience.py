"""Décorateur universel de résilience réseau avec rétrogradation exponentielle (Anti-429 & Retries)."""

import functools
import random
import time
from typing import Any, Callable, TypeVar
import httpx

from src.utils.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


def resilient_network_call(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    exponential_factor: float = 2.0,
    handle_429: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Callable[[F], F]:
    """Décorateur pour requêtes réseau instables ou soumises à un contrôle de débit.

    Gère les erreurs transitoires (ConnectError, Timeout, etc.) et les codes HTTP 429.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    attempt += 1
                    if handle_429 and e.response.status_code == 429:
                        if attempt > max_retries:
                            logger.warning(f"[RESILIENCE] Nombre maximal de retries ({max_retries}) dépassé sur 429.")
                            raise

                        # Extraire le délai Retry-After si présent
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            wait_time = float(retry_after)
                        else:
                            jitter = random.uniform(0.1, 0.5)
                            wait_time = min(max_delay, (base_delay * (exponential_factor ** (attempt - 1))) + jitter)

                        logger.info(f"[RESILIENCE] HTTP 429 reçu. Attente de {wait_time:.2f}s (tentative {attempt}/{max_retries})...")
                        sleep_fn(wait_time)
                        continue
                    raise

                except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.warning(f"[RESILIENCE] Nombre maximal de retries ({max_retries}) dépassé sur erreur réseau: {e}")
                        raise

                    jitter = random.uniform(0.1, 0.5)
                    wait_time = min(max_delay, (base_delay * (exponential_factor ** (attempt - 1))) + jitter)
                    logger.info(f"[RESILIENCE] Erreur réseau transitoire ({type(e).__name__}). Attente {wait_time:.2f}s...")
                    sleep_fn(wait_time)

        return wrapper  # type: ignore[return-value]

    return decorator
