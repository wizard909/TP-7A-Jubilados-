from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from .solicitudes.dominio import ErrorSolicitud, TipoError

ESTADOS_HTTP = {
    TipoError.ENTRADA: 400,
    TipoError.PERMISO: 403,
    TipoError.NO_ENCONTRADA: 404,
    TipoError.CONFLICTO: 409,
    TipoError.PADRON: 503,
}

TITULOS = {
    400: "Entrada inválida", 401: "Autenticación requerida", 403: "Acceso denegado",
    404: "No encontrado", 409: "Conflicto", 503: "Servicio no disponible",
}


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
    )


def request_error(request: Request, status: int, title: str, detail: str, templates: Jinja2Templates):
    path = request.url.path
    accepts_html = any(
        entry.split(";", 1)[0].strip() == "text/html"
        for entry in request.headers.get("accept", "").split(",")
    )
    if (path.startswith("/web/") or path == "/auth/callback") and accepts_html:
        return templates.TemplateResponse(
            request, "error.html",
            {"user": request.session.get("user"), "title": title, "detail": detail,
             "show_login": status == 401 or path == "/auth/callback"},
            status_code=status,
            headers={"Vary": "Accept", "Cache-Control": "no-store"},
        )
    return problem(status, title, detail)


def instalar_manejadores(app, templates: Jinja2Templates):
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return request_error(request, exc.status_code, TITULOS.get(exc.status_code, "Error"), str(exc.detail), templates)

    @app.exception_handler(ErrorSolicitud)
    async def application_error(request: Request, exc: ErrorSolicitud):
        status = ESTADOS_HTTP[exc.tipo]
        return request_error(request, status, TITULOS[status], str(exc), templates)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return request_error(request, 400, TITULOS[400], "Revisá los datos enviados.", templates)
