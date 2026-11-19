from fastapi import Depends
from sqlalchemy.orm import Session

from .configuracion import DEMO_IDENTITIES
from .integraciones.padron import consultar_padron
from .persistencia import db_session
from .solicitudes.repositorio import SqlAlchemySolicitudes
from .solicitudes.servicio import ServicioSolicitudes


def servicio_solicitudes(session: Session = Depends(db_session)) -> ServicioSolicitudes:
    return ServicioSolicitudes(SqlAlchemySolicitudes(session), consultar_padron, DEMO_IDENTITIES)
