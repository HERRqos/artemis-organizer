import redis


class RedisDedupe:
    """SET NX EX — first writer wins, key expires so Redis stays small."""

    def __init__(self, url: str, ttl_seconds: int = 24 * 3600, prefix: str = "seen:"):
        self._r = redis.Redis.from_url(url, decode_responses=True,socket_keepalive=True)
        self._ttl = ttl_seconds
        self._prefix = prefix

    def seen(self, key: str) -> bool:
        return not self._r.set(self._prefix + key, "1", nx=True, ex=self._ttl)
