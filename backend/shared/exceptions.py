"""
Custom exceptions for the application.
DRY: Used by both Django and FastAPI.
"""


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ConflictException(AppException):
    """" Conflicting error """
    def __init__(self, message:str, code:str="error"):
        self.message = message 
        self.code=code 
        super().__init__(message)


class NotFoundException(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with id '{identifier}' not found",
            code="not_found"
        )


class ValidationException(AppException):
    """Validation error exception."""

    def __init__(self, message: str):
        super().__init__(message=message, code="validation_error")


class AuthenticationException(AppException):
    """Authentication error exception."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, code="authentication_error")


class AuthorizationException(AppException):
    """Authorization error exception."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, code="authorization_error")


class RateLimitException(AppException):
    """Rate limit exceeded exception."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, code="rate_limit_exceeded")


class QuotaExceededException(AppException):
    """Usage quota exceeded exception."""

    def __init__(self, resource: str, limit: int):
        super().__init__(
            message=f"{resource} quota exceeded. Limit: {limit}",
            code="quota_exceeded"
        )


class ExternalServiceException(AppException):
    """External service error exception."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} error: {message}",
            code="external_service_error"
        )


# Exception mappings for FastAPI
# Used in exception_handlers.py
EXCEPTION_STATUS_MAP = {
    NotFoundException: 404,
    ValidationException: 422,
    AuthenticationException: 401,
    AuthorizationException: 403,
    RateLimitException: 429,
    QuotaExceededException: 402,
    ExternalServiceException: 502,
}
