from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Add Content-Security-Policy header to all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(settings, 'CSP_ENABLED', True):
            return response

        # Skip CSP for admin (it uses inline scripts/styles extensively)
        if request.path.startswith('/admin/'):
            return response

        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://www.paypal.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https://www.paypal.com https://accounts.google.com https://oauth2.googleapis.com",
            "frame-src https://www.paypal.com https://www.sandbox.paypal.com",
            "base-uri 'self'",
            "form-action 'self' https://www.paypal.com https://www.sandbox.paypal.com https://accounts.google.com",
            "object-src 'none'",
        ]

        response['Content-Security-Policy'] = '; '.join(csp_directives)
        return response
