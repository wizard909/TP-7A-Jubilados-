import httpx

from app.configuracion import PADRON_URL
from app.solicitudes.dominio import ResultadoPadron

CONDICIONES = {
    "jubilado": ResultadoPadron.ELEGIBLE,
    "pensionado": ResultadoPadron.ELEGIBLE,
    "no_registrado": ResultadoPadron.NO_ELEGIBLE,
}


def consultar_padron(identificador: str) -> ResultadoPadron:
    try:
        response = httpx.post(f"{PADRON_URL}/verificaciones", json={"identificador": identificador}, timeout=3.0)
    except httpx.RequestError:
        return ResultadoPadron.SIN_RESPUESTA
    if response.status_code == 503:
        return ResultadoPadron.NO_DISPONIBLE
    if response.status_code != 200:
        return ResultadoPadron.INESPERADO
    try:
        result = response.json()
    except ValueError:
        return ResultadoPadron.INVALIDO
    condition = result.get("condicion") if isinstance(result, dict) else None
    if not isinstance(condition, str):
        return ResultadoPadron.INVALIDO
    return CONDICIONES.get(condition, ResultadoPadron.INVALIDO)
