from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

app = FastAPI(title="Padrón simulado")


class Consulta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identificador: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        media_type="application/problem+json",
        content={"type": "about:blank", "title": "Entrada inválida", "status": 400,
                 "detail": "Indicá un identificador ficticio no vacío y sin campos adicionales."},
    )


@app.post("/verificaciones")
def verificar(consulta: Consulta):
    if consulta.identificador == "ERR-004":
        return JSONResponse(
            status_code=503,
            media_type="application/problem+json",
            content={"type": "about:blank", "title": "Padrón no disponible", "status": 503},
        )
    condicion = {
        "JUB-001": "jubilado",
        "PEN-002": "pensionado",
    }.get(consulta.identificador, "no_registrado")
    return {"condicion": condicion}
