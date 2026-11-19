from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum, auto
from uuid import uuid4

PENDIENTE = "pendiente"
APROBADA = "aprobada"
RECHAZADA = "rechazada"


class TipoError(Enum):
    ENTRADA = auto()
    PERMISO = auto()
    NO_ENCONTRADA = auto()
    CONFLICTO = auto()
    PADRON = auto()


class ErrorSolicitud(Exception):
    def __init__(self, tipo: TipoError, detalle: str):
        super().__init__(detalle)
        self.tipo = tipo


class ResultadoPadron(Enum):
    ELEGIBLE = auto()
    NO_ELEGIBLE = auto()
    SIN_RESPUESTA = auto()
    NO_DISPONIBLE = auto()
    INESPERADO = auto()
    INVALIDO = auto()


@dataclass(frozen=True)
class Solicitud:
    id: str
    beneficio_id: str
    solicitante_id: str
    solicitante_nombre: str
    estado: str
    creada_en: datetime
    resuelta_en: datetime | None = None
    motivo: str | None = None
    agente_id: str | None = None

    @classmethod
    def presentar(cls, beneficio: str, solicitante_id: str, solicitante_nombre: str):
        return cls(str(uuid4()), beneficio, solicitante_id, solicitante_nombre,
                   PENDIENTE, datetime.now(timezone.utc))

    def validar_decision(self, estado: str, motivo: str):
        if self.estado != PENDIENTE:
            raise ErrorSolicitud(TipoError.CONFLICTO, "La solicitud ya tiene una decisión")
        if estado not in {APROBADA, RECHAZADA} or not motivo.strip():
            raise ErrorSolicitud(TipoError.ENTRADA, "Indicá una decisión y un motivo")

    def decidir(self, estado: str, motivo: str, agente_id: str, padron: ResultadoPadron | None):
        self.validar_decision(estado, motivo)
        if estado == APROBADA and padron is not ResultadoPadron.ELEGIBLE:
            raise ErrorSolicitud(TipoError.CONFLICTO, "El padrón no confirma la condición requerida")
        return replace(self, estado=estado, motivo=motivo.strip()[:500],
                       resuelta_en=datetime.now(timezone.utc), agente_id=agente_id)
