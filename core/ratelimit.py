from django.core.cache import cache


def is_rate_limited(key, limit, window):
    """
    Return True if more than `limit` requests have been seen for `key`
    within `window` seconds. Uses the Django cache backend (Redis in prod).
    Uses atomic INCR: the window starts on the first request and expires
    naturally — no sliding reset.
    """
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        return False
    return count > limit
