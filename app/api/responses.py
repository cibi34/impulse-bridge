from typing import Any
from fastapi.responses import JSONResponse


CODE_OK = 0
CODE_COLLECTION_NOT_FOUND = 1
CODE_ASSET_NOT_FOUND = 2
CODE_UPSTREAM_UNAVAILABLE = 10
CODE_UPSTREAM_RATE_LIMITED = 11
CODE_UPSTREAM_MALFORMED = 12
CODE_CONFIG_ERROR = 20
CODE_INTERNAL = 99


_HTTP_STATUS_BY_CODE: dict[int, int] = {
    CODE_OK: 200,
    CODE_COLLECTION_NOT_FOUND: 404,
    CODE_ASSET_NOT_FOUND: 404,
    CODE_UPSTREAM_UNAVAILABLE: 503,
    CODE_UPSTREAM_RATE_LIMITED: 503,
    CODE_UPSTREAM_MALFORMED: 502,
    CODE_CONFIG_ERROR: 500,
    CODE_INTERNAL: 500,
}


def impulse_response(
    data: Any,
    code: int = CODE_OK,
    message: str = "OK",
    http_status: int | None = None,
) -> JSONResponse:
    """Wrap any payload in the Impulse API response schema {code, message, data}."""
    status = http_status if http_status is not None else _HTTP_STATUS_BY_CODE.get(code, 200)
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "data": data},
    )
