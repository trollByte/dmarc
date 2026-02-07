"""
Security Headers Middleware

Adds security headers to all responses to protect against common web vulnerabilities.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables browser XSS filtering
    - Strict-Transport-Security: Enforces HTTPS
    - Content-Security-Policy: Controls resource loading
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        enable_csp: bool = True,
        csp_directives: dict = None,
        frame_options: str = "DENY",
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.frame_options = frame_options

        # Default CSP directives
        self.csp_directives = csp_directives or {
            "default-src": "'self'",
            "script-src": "'self' https://cdn.jsdelivr.net https://unpkg.com",
            "style-src": "'self' 'unsafe-inline' https://unpkg.com",  # unsafe-inline required for Chart.js canvas rendering and Leaflet
            "img-src": "'self' data: https:",  # Allow data URIs (Chart.js) and HTTPS images (map tiles)
            "font-src": "'self' https:",
            "connect-src": "'self' https:",  # Allow API calls
            "frame-ancestors": "'none'",  # Prevent framing
            "base-uri": "'self'",
            "form-action": "'self'",
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = self.frame_options

        # Enable XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable browser features we don't need
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # HSTS - only add for HTTPS requests or when explicitly enabled
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )

        # Content Security Policy
        if self.enable_csp:
            csp_value = "; ".join(
                f"{key} {value}" for key, value in self.csp_directives.items()
            )
            response.headers["Content-Security-Policy"] = csp_value

        # Prevent caching of sensitive responses
        if request.url.path.startswith(("/auth/", "/api/users/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates the Host header to prevent host header injection attacks.
    """

    def __init__(self, app, allowed_hosts: list[str] = None, allow_any: bool = False):
        super().__init__(app)
        self.allowed_hosts = set(allowed_hosts or [])
        self.allow_any = allow_any

        # Always allow localhost variants for development
        self.allowed_hosts.update([
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ])

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.allow_any:
            return await call_next(request)

        host = request.headers.get("host", "").split(":")[0]  # Remove port

        if host not in self.allowed_hosts:
            logger.warning(f"Rejected request with invalid host header: {host}")
            return Response(
                content='{"detail": "Invalid host header"}',
                status_code=400,
                media_type="application/json"
            )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that limits the size of incoming requests to prevent DoS attacks.
    """

    def __init__(self, app, max_content_length: int = 50 * 1024 * 1024):  # 50MB default
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                if int(content_length) > self.max_content_length:
                    logger.warning(
                        f"Rejected request with content length {content_length} "
                        f"(max: {self.max_content_length})"
                    )
                    return Response(
                        content='{"detail": "Request body too large"}',
                        status_code=413,
                        media_type="application/json"
                    )
            except ValueError:
                pass  # Invalid content-length header, let it through

        return await call_next(request)
