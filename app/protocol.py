from __future__ import annotations

from typing import Any


def ok_response(message_type: str, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {'type': message_type, 'request_id': request_id, 'ok': True, 'payload': payload}


def error_response(request_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        'type': 'error',
        'request_id': request_id,
        'ok': False,
        'error': {'code': code, 'message': message},
    }
