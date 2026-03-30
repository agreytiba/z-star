"""
Custom middleware for Zuristar backend.
"""
import time
import logging
from django.http import JsonResponse

logger = logging.getLogger('api')


class HealthCheckMiddleware:
    """
    Intercepts GET /health/ and returns a quick JSON status response
    without touching the database or going through DRF.
    Used by load balancers and uptime monitors.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/health/' and request.method == 'GET':
            return JsonResponse({'status': 'ok', 'service': 'zuristar-api'})
        return self.get_response(request)


class RequestTimingMiddleware:
    """
    Adds an X-Response-Time header (in ms) to every response and logs
    slow requests (>1 s) at WARNING level so they're easy to find.
    """
    SLOW_REQUEST_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        response['X-Response-Time'] = f'{elapsed_ms}ms'

        if elapsed_ms > self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                'SLOW REQUEST %s %s – %dms',
                request.method,
                request.path,
                elapsed_ms,
            )

        return response
