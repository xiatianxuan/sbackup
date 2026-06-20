"""重试工具：指数退避重试机制"""

import random
import time
import logging

logger = logging.getLogger(__name__)


def with_retry(
    max_retries: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """指数退避重试装饰器"""

    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base**attempt),
                            max_delay,
                        )
                        if jitter:
                            delay += random.uniform(0, delay * 0.5)
                        logger.warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            e,
                            delay,
                        )
                        time.sleep(delay)
            raise last_exc

        return wrapper

    return decorator


def retry_call(func, *args, max_retries=2, base_delay=0.5, **kwargs):
    """直接调用带重试的函数"""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), 60.0)
                delay += random.uniform(0, delay * 0.5)
                logger.warning(
                    "Retry %d/%d after %.1fs: %s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    e,
                )
                time.sleep(delay)
    raise last_exc
