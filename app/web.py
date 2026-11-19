from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .errores_http import ESTADOS_HTTP
from .dependencias import servicio_solicitudes
from .seguridad import actor_from_claims, check_csrf, web_user
from .solicitudes.dominio import PENDIENTE, ErrorSolicitud, Solicitud, TipoError
from .solicitudes.servicio import BENEFICIOS, NOMBRES_BENEFICIOS, ServicioSolicitudes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Local time for contemporary records in the Argentine municipal demo.
PORTAL_TIMEZONE = timezone(timedelta(hours=-3))


def portal_date(value: datetime) -> str:
    # SQLite, used for local tests, can return stored UTC timestamps without an offset.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(PORTAL_TIMEZONE).strftime("%d/%m/%Y")


templates.env.filters["benefit_name"] = lambda value: NOMBRES_BENEFICIOS.get(value, value)
templates.env.filters["portal_date"] = portal_date


@router.get("/", response_class=HTMLResponse)
def home(request: Request, service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    user = request.session.get("user")
    items = []
    if user:
        actor = actor_from_claims(user)
        if "agente" in actor.roles:
            items = service.pendientes(actor, PENDIENTE, recientes=True)
        else:
            items = service.propias(actor)
    return templates.TemplateResponse(request, "home.html", {
        "user": user, "items": items, "benefits": BENEFICIOS, "csrf": request.session.get("csrf", ""),
    })


@router.post("/web/solicitudes")
def web_create(request: Request, beneficio: str = Form(), csrf: str = Form(),
               service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    check_csrf(request, csrf)
    item = service.presentar(actor_from_claims(web_user(request)), beneficio)
    return RedirectResponse(f"/web/solicitudes/{item.id}", status_code=303)


@router.get("/web/solicitudes/{item_id}", response_class=HTMLResponse)
def web_detail(item_id: str, request: Request, service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    user = web_user(request)
    try:
        item = service.consultar(actor_from_claims(user), item_id)
    except ErrorSolicitud as exc:
        if exc.tipo is TipoError.PERMISO:
            raise HTTPException(403, "No podés ver una solicitud ajena") from exc
        raise
    return render_web_detail(request, item, user)


def render_web_detail(request: Request, item: Solicitud, user: dict, error: HTTPException | None = None, reason: str = ""):
    return templates.TemplateResponse(
        request, "detail.html",
        {"item": item, "user": user, "csrf": request.session.get("csrf", ""),
         "decision_error": error.detail if error else None, "submitted_reason": reason},
        status_code=error.status_code if error else 200,
    )


@router.post("/web/solicitudes/{item_id}/decision")
def web_decide(item_id: str, request: Request, estado: str = Form(), motivo: str = Form(), csrf: str = Form(),
               service: ServicioSolicitudes = Depends(servicio_solicitudes)):
    check_csrf(request, csrf)
    user = web_user(request)
    actor = actor_from_claims(user)
    try:
        service.decidir(actor, item_id, estado, motivo)
    except ErrorSolicitud as exc:
        if exc.tipo not in {TipoError.ENTRADA, TipoError.CONFLICTO, TipoError.PADRON}:
            raise
        error = HTTPException(ESTADOS_HTTP[exc.tipo], str(exc))
        return render_web_detail(request, service.consultar(actor, item_id), user, error=error, reason=motivo[:500])
    return RedirectResponse(f"/web/solicitudes/{item_id}", status_code=303)
