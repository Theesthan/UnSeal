"""Every error leaves the API as `{"error": "<code>", "detail": ...}` (docs/api.md).

Validation details keep the field location and message but never the submitted value, which can
hold a user's grievance text.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from unseal.llm.client import ModelBusy, ModelIncomplete, ModelOutputInvalid
from unseal.services.appeals import InvalidGrounds
from unseal.services.cases import Blocked, InvalidPaymentMode, NotFound, WrongStatus


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: Any = None) -> None:
        super().__init__(code)
        self.status, self.code, self.detail = status, code, detail


def error_response(status: int, code: str, detail: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"error": code}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(body, status_code=status)


# Model failures, mapped to what the user sees (docs/api.md).
_MODEL_ERRORS: dict[type[Exception], tuple[int, str]] = {
    ModelBusy: (503, "busy"),
    ModelOutputInvalid: (422, "ask_user"),
    ModelIncomplete: (422, "incomplete"),
}
_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def install(app: FastAPI) -> None:
    async def api_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ApiError)
        return error_response(exc.status, exc.code, exc.detail)

    async def model_error(_: Request, exc: Exception) -> JSONResponse:
        status, code = _MODEL_ERRORS[type(exc)]
        return error_response(status, code)

    async def invalid(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        fields = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return error_response(400, "invalid", fields)

    async def http_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)
        return error_response(exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"))

    app.add_exception_handler(ApiError, api_error)
    for model_exc in _MODEL_ERRORS:
        app.add_exception_handler(model_exc, model_error)
    app.add_exception_handler(RequestValidationError, invalid)
    app.add_exception_handler(HTTPException, http_error)

    async def not_found(_: Request, __: Exception) -> JSONResponse:
        return error_response(404, "not_found")

    async def wrong_status(_: Request, __: Exception) -> JSONResponse:
        return error_response(409, "wrong_status")

    async def blocked(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, Blocked)
        return error_response(409, "blocked", {"flags": [f.model_dump() for f in exc.flags]})

    async def invalid_payment_mode(_: Request, __: Exception) -> JSONResponse:
        return error_response(400, "invalid_payment_mode")

    async def invalid_grounds(_: Request, __: Exception) -> JSONResponse:
        return error_response(400, "invalid_grounds")

    app.add_exception_handler(Blocked, blocked)
    app.add_exception_handler(InvalidGrounds, invalid_grounds)
    app.add_exception_handler(InvalidPaymentMode, invalid_payment_mode)
    app.add_exception_handler(NotFound, not_found)
    app.add_exception_handler(WrongStatus, wrong_status)
