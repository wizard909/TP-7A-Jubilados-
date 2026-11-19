from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .dominio import APROBADA, PENDIENTE, ErrorSolicitud, ResultadoPadron, Solicitud, TipoError

BENEFICIOS = [
    {"id": "tarifa-social", "nombre": "Tarifa social"},
    {"id": "descuento-transporte", "nombre": "Descuento en transporte"},
]
NOMBRES_BENEFICIOS = {beneficio["id"]: beneficio["nombre"] for beneficio in BENEFICIOS}

ERRORES_PADRON = {
    ResultadoPadron.SIN_RESPUESTA: "No se pudo consultar el padrón; la solicitud sigue pendiente",
    ResultadoPadron.NO_DISPONIBLE: "El padrón no está disponible; la solicitud sigue pendiente",
    ResultadoPadron.INESPERADO: "El padrón devolvió una respuesta inesperada",
    ResultadoPadron.INVALIDO: "El padrón devolvió una respuesta inesperada; la solicitud sigue pendiente",
}


class RepositorioSolicitudes(Protocol):
    def obtener(self, id: str) -> Solicitud | None: ...
    def agregar(self, solicitud: Solicitud) -> Solicitud: ...
    def listar_pendientes(self, *, recientes: bool = False) -> list[Solicitud]: ...
    def listar_propias(self, solicitante_id: str) -> list[Solicitud]: ...
    def guardar_si_pendiente(self, solicitud: Solicitud) -> Solicitud | None: ...


@dataclass(frozen=True)
class Actor:
    id: str
    nombre: str
    roles: frozenset[str]

    def exigir(self, rol: str):
        if rol not in self.roles:
            raise ErrorSolicitud(TipoError.PERMISO, "Tu rol no permite esta operación")


@dataclass(frozen=True)
class ServicioSolicitudes:
    repositorio: RepositorioSolicitudes
    consultar_padron: Callable[[str], ResultadoPadron]
    identidades: Mapping[str, str]

    def presentar(self, actor: Actor, beneficio: str) -> Solicitud:
        actor.exigir("vecino")
        if beneficio not in NOMBRES_BENEFICIOS:
            raise ErrorSolicitud(TipoError.ENTRADA, "Beneficio inexistente")
        if actor.nombre not in self.identidades:
            raise ErrorSolicitud(TipoError.CONFLICTO, "La cuenta no tiene vínculo de prueba con el padrón")
        return self.repositorio.agregar(Solicitud.presentar(beneficio, actor.id, actor.nombre))

    def pendientes(self, actor: Actor, estado: str, *, recientes: bool = False) -> list[Solicitud]:
        actor.exigir("agente")
        if estado != PENDIENTE:
            raise ErrorSolicitud(TipoError.ENTRADA, "Solo se admite estado=pendiente en este corte")
        return self.repositorio.listar_pendientes(recientes=recientes)

    def propias(self, actor: Actor) -> list[Solicitud]:
        return self.repositorio.listar_propias(actor.id)

    def _obtener(self, id: str) -> Solicitud:
        solicitud = self.repositorio.obtener(id)
        if solicitud is None:
            raise ErrorSolicitud(TipoError.NO_ENCONTRADA, "Solicitud inexistente")
        return solicitud

    def consultar(self, actor: Actor, id: str) -> Solicitud:
        solicitud = self._obtener(id)
        if "agente" not in actor.roles and solicitud.solicitante_id != actor.id:
            raise ErrorSolicitud(TipoError.PERMISO, "No podés consultar una solicitud ajena")
        return solicitud

    def decidir(self, actor: Actor, id: str, estado: str, motivo: str) -> Solicitud:
        actor.exigir("agente")
        solicitud = self._obtener(id)
        solicitud.validar_decision(estado, motivo)
        padron = None
        if estado == APROBADA:
            identificador = self.identidades.get(solicitud.solicitante_nombre)
            if not identificador:
                raise ErrorSolicitud(TipoError.CONFLICTO, "No existe vínculo con el padrón")
            padron = self.consultar_padron(identificador)
            if padron in ERRORES_PADRON:
                raise ErrorSolicitud(TipoError.PADRON, ERRORES_PADRON[padron])
        decidida = solicitud.decidir(estado, motivo, actor.id, padron)
        guardada = self.repositorio.guardar_si_pendiente(decidida)
        if guardada is None:
            raise ErrorSolicitud(TipoError.CONFLICTO, "La solicitud ya tiene una decisión")
        return guardada
