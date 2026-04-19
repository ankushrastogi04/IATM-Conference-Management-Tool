import time
from django.core.cache import cache
from django.http import HttpResponse


# Rate limit config: URL name -> (max_requests, window_seconds)
RATE_LIMITS = {
    'login': (5, 300),           # 5 attempts per 5 minutes
    'register': (3, 600),        # 3 registrations per 10 minutes
    'password_reset': (3, 600),  # 3 resets per 10 minutes
    'payment_checkout': (10, 300),  # 10 per 5 minutes
    'bulk_email': (5, 3600),     # 5 bulk sends per hour
    'send_message': (20, 300),   # 20 messages per 5 minutes
    'export_my_data': (3, 3600), # 3 exports per hour
}


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST':
            return self.get_response(request)

        url_name = getattr(request.resolver_match, 'url_name', None)
        if not url_name or url_name not in RATE_LIMITS:
            return self.get_response(request)

        max_requests, window = RATE_LIMITS[url_name]
        ip = get_client_ip(request)
        cache_key = f'ratelimit:{url_name}:{ip}'

        request_log = cache.get(cache_key, [])
        now = time.time()

        # Remove expired entries
        request_log = [t for t in request_log if now - t < window]

        if len(request_log) >= max_requests:
            retry_after = int(window - (now - request_log[0]))
            response = HttpResponse(
                'Too many requests. Please try again later.',
                status=429,
                content_type='text/plain',
            )
            response['Retry-After'] = str(retry_after)
            return response

        request_log.append(now)
        cache.set(cache_key, request_log, window)

        return self.get_response(request)
