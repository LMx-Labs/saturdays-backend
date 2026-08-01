from typing import Any, Optional, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse

class SaturdaysException(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class DomainInvariantViolationError(SaturdaysException):
    def __init__(self, message: str, error_code: str = "DOMAIN_INVARIANT_VIOLATION", details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code=error_code, message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)

class EntityNotFoundError(SaturdaysException):
    def __init__(self, message: str, error_code: str = "ENTITY_NOT_FOUND", details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code=error_code, message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)

class UnauthorizedError(SaturdaysException):
    def __init__(self, message: str = "Invalid or missing authentication credentials", error_code: str = "UNAUTHORIZED"):
        super().__init__(error_code=error_code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)

class ForbiddenError(SaturdaysException):
    def __init__(self, message: str = "Permission denied for this resource", error_code: str = "FORBIDDEN"):
        super().__init__(error_code=error_code, message=message, status_code=status.HTTP_403_FORBIDDEN)

class ConflictError(SaturdaysException):
    def __init__(self, message: str, error_code: str = "RESOURCE_CONFLICT", details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code=error_code, message=message, status_code=status.HTTP_409_CONFLICT, details=details)

class InventoryOutOfStockError(SaturdaysException):
    def __init__(self, message: str = "Item is out of stock", details: Optional[Dict[str, Any]] = None):
        super().__init__(error_code="INVENTORY_OUT_OF_STOCK", message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)

async def saturdays_exception_handler(request: Request, exc: SaturdaysException) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "correlation_id": correlation_id
        }
    )
