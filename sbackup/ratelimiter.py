"""带宽限速器：Token Bucket 算法"""

import time
import threading


class RateLimiter:
    """令牌桶速率限制器

    用法::
        limiter = RateLimiter(1024 * 1024)  # 1 MB/s
        while data := file.read(chunk_size):
            limiter.wait(len(data))
            upload(data)
    """

    def __init__(self, bytes_per_second: float):
        self._rate = bytes_per_second
        self._tokens = bytes_per_second
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def wait(self, bytes_consumed: int) -> None:
        """等待直到有足够的令牌"""
        if self._rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens += elapsed * self._rate
            self._last = now
            if self._tokens > self._rate:
                self._tokens = self._rate
            if self._tokens >= bytes_consumed:
                self._tokens -= bytes_consumed
                return
            deficit = bytes_consumed - self._tokens
            sleep_time = deficit / self._rate
            self._tokens = 0
            time.sleep(sleep_time)
