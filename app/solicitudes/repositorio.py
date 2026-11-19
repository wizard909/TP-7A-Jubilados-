from dataclasses import asdict, fields
from datetime import datetime

from sqlalchemy import DateTime, String, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.persistencia import Base

from .dominio import PENDIENTE, Solicitud


class SolicitudRow(Base):
    __tablename__ = "solicitudes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    beneficio_id: Mapped[str] = mapped_column(String(80), nullable=False)
    solicitante_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    solicitante_nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default=PENDIENTE)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[str | None] = mapped_column(String(500))
    agente_id: Mapped[str | None] = mapped_column(String(160))


def to_domain(row: SolicitudRow) -> Solicitud:
    return Solicitud(**{field.name: getattr(row, field.name) for field in fields(Solicitud)})


class SqlAlchemySolicitudes:
    def __init__(self, session: Session):
        self.session = session

    def obtener(self, id: str) -> Solicitud | None:
        row = self.session.get(SolicitudRow, id)
        return to_domain(row) if row else None

    def agregar(self, solicitud: Solicitud) -> Solicitud:
        row = SolicitudRow(**asdict(solicitud))
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return to_domain(row)

    def listar_pendientes(self, *, recientes: bool = False) -> list[Solicitud]:
        query = select(SolicitudRow).where(SolicitudRow.estado == PENDIENTE)
        if recientes:
            query = query.order_by(SolicitudRow.creada_en.desc())
        return [to_domain(row) for row in self.session.scalars(query)]

    def listar_propias(self, solicitante_id: str) -> list[Solicitud]:
        query = select(SolicitudRow).where(SolicitudRow.solicitante_id == solicitante_id)
        query = query.order_by(SolicitudRow.creada_en.desc())
        return [to_domain(row) for row in self.session.scalars(query)]

    def guardar_si_pendiente(self, solicitud: Solicitud) -> Solicitud | None:
        # The database arbitrates concurrent decisions with this conditional write.
        statement = (
            update(SolicitudRow)
            .where(SolicitudRow.id == solicitud.id, SolicitudRow.estado == PENDIENTE)
            .values(estado=solicitud.estado, motivo=solicitud.motivo,
                    resuelta_en=solicitud.resuelta_en, agente_id=solicitud.agente_id)
            .returning(SolicitudRow)
            .execution_options(populate_existing=True)
        )
        row = self.session.scalars(statement).one_or_none()
        saved = to_domain(row) if row else None
        self.session.commit()
        return saved
