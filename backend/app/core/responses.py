from typing import Any
from uuid import uuid4

from fastapi import Request


def success(request: Request, data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "error": None,
        "requestId": getattr(request.state, "request_id", str(uuid4())),
    }


def failure(request: Request, code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
        "requestId": getattr(request.state, "request_id", str(uuid4())),
    }
