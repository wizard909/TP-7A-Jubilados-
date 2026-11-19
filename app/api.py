from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .dependencias import servicio_solicitudes
from .seguridad import actor_from_claims, api_user
from .solicitudes.dominio import Solicitud
from .solicitudes.servicio import BENEFICIOS, ServicioSolicitudes

router = APIRouter(prefix="/api/v1")


def view_model(item: Solicitud) -> dict:
    return {
        "id": item.id,
        "beneficioId": item.beneficio_id,
        "solicitanteId": item.solicitante_id,
        "estado": item.estado,
        "creadaEn": item.creada_en.isoformat(),
        "resueltaEn": item.resuelta_en.isoformat() if item.resuelta_en else None,
        "motivo": item.motivo,
    }


class NewApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    beneficioId: str


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: str
    motivo: str


@router.get("/beneficios")
def list_benefits():
    return BENEFICIOS


@router.post("/solicitudes", status_code=201)
def post_application(body: NewApplication, user: dict = Depends(api_user),
                     service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    item = service.presentar(actor_from_claims(user), body.beneficioId)
    return JSONResponse(status_code=201, headers={"Location": f"/api/v1/solicitudes/{item.id}"},
                        content=view_model(item))


@router.get("/solicitudes")
def list_applications(estado: str, user: dict = Depends(api_user),
                      service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    return [view_model(item) for item in service.pendientes(actor_from_claims(user), estado)]


@router.get("/solicitudes/{id}")
def get_application(id: str, user: dict = Depends(api_user),
                    service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    return view_model(service.consultar(actor_from_claims(user), id))


@router.patch("/solicitudes/{id}")
def patch_application(id: str, body: Decision, user: dict = Depends(api_user),
                      service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    item = service.decidir(actor_from_claims(user), id, body.estado, body.motivo)
    return view_model(item)
