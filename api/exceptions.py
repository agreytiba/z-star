import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('api')


def custom_exception_handler(exc, context):
    """
    Normalise all DRF error responses to a consistent JSON envelope:

        { "error": "...", "detail": {...} }

    Unhandled server errors are logged and returned as a 500 with a safe message.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Flatten DRF's varied error shapes into a single 'error' string
        data = response.data
        if isinstance(data, dict):
            # Pull out 'detail' key or stringify the whole dict
            detail = data.get('detail', data)
            error_msg = str(detail) if not isinstance(detail, dict) else 'Validation error'
        elif isinstance(data, list):
            error_msg = '; '.join(str(e) for e in data)
        else:
            error_msg = str(data)

        response.data = {
            'error':   error_msg,
            'detail':  data,
            'status':  response.status_code,
        }
    else:
        # Unhandled exception – log it, return safe 500
        logger.exception(
            'Unhandled exception in %s %s',
            context.get('request').method if context.get('request') else '?',
            context.get('request').path   if context.get('request') else '?',
            exc_info=exc,
        )
        response = Response(
            {
                'error':  'An unexpected error occurred. Please try again later.',
                'status': 500,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
