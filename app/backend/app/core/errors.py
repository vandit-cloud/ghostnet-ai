import uuid

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(code: str, message: str, request_id: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, request_id),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
    )
