from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination used across all list endpoints.
    Clients can override page_size up to max_page_size via ?page_size=N.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count':    self.page.paginator.count,
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'results':  data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count':    {'type': 'integer'},
                'next':     {'type': 'string', 'nullable': True},
                'previous': {'type': 'string', 'nullable': True},
                'results':  schema,
            },
        }


class LargeResultsSetPagination(PageNumberPagination):
    """For admin bulk-data endpoints."""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500
