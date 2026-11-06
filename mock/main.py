from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Padrón simulado")


class Consulta(BaseModel):
    identificador: str


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
