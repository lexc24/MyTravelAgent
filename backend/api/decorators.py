from functools import wraps

from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.response import Response


def rate_limit_api(key="user", rate="30/m", method="ALL"):
    """
    Custom rate limiting decorator for API views
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Apply rate limiting
            limited = getattr(request, "limited", False)

            @ratelimit(key=key, rate=rate, method=method)
            def check_limit(request, *args, **kwargs):
                return view_func(request, *args, **kwargs)

            response = check_limit(request, *args, **kwargs)

            # Check if rate limited
            if getattr(request, "limited", False):
                return Response(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            return response

        return wrapped_view

    return decorator
