import base64
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./municipio.db")
PADRON_URL = os.environ.get("PADRON_URL", "http://localhost:8090")
KC_PUBLIC = os.environ.get("KEYCLOAK_PUBLIC", "http://localhost:8180/realms/municipio")
KC_INTERNAL = os.environ.get("KEYCLOAK_INTERNAL", KC_PUBLIC)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "solo-desarrollo-local")
DEMO_IDENTITIES = json.loads(os.environ.get("DEMO_IDENTITIES", '{"vecino1":"JUB-001","vecino2":"NO-003"}'))
REDIRECT_URI = os.environ.get("APP_PUBLIC_URL", "http://localhost:8080").rstrip("/") + "/auth/callback"
BENEFITS = [
    {"id": "tarifa-social", "nombre": "Tarifa social"},
    {"id": "descuento-transporte", "nombre": "Descuento en transporte"},
]


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "solicitudes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    beneficio_id: Mapped[str] = mapped_column(String(80), nullable=False)
    solicitante_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    solicitante_nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[str | None] = mapped_column(String(500))
    agente_id: Mapped[str | None] = mapped_column(String(160))


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine)
app = FastAPI(title="Beneficios municipales", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
templates = Jinja2Templates(directory="app/templates")
jwks = PyJWKClient(f"{KC_INTERNAL}/protocol/openid-connect/certs")


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(engine)


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
    )


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    titles = {400: "Entrada inválida", 401: "Autenticación requerida", 403: "Acceso denegado", 404: "No encontrado", 409: "Conflicto", 503: "Servicio no disponible"}
    return problem(exc.status_code, titles.get(exc.status_code, "Error"), str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return problem(400, "Entrada inválida", "Revisá los datos enviados.")


def db_session():
    with SessionLocal() as session:
        yield session


def decode_token(token: str) -> dict:
    try:
        key = jwks.get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["RS256"], audience="municipio-api", issuer=KC_PUBLIC)
    except Exception as exc:
        raise HTTPException(401, "Token de acceso inválido o vencido") from exc


def api_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta el token de acceso")
    return decode_token(authorization[7:])


def role(user: dict, expected: str):
    if expected not in user.get("realm_access", {}).get("roles", []):
        raise HTTPException(403, "Tu rol no permite esta operación")


def view_model(item: Application) -> dict:
    return {
        "id": item.id,
        "beneficioId": item.beneficio_id,
        "solicitanteId": item.solicitante_id,
        "estado": item.estado,
        "creadaEn": item.creada_en.isoformat(),
        "resueltaEn": item.resuelta_en.isoformat() if item.resuelta_en else None,
        "motivo": item.motivo,
    }


def create_application(session: Session, user: dict, benefit: str) -> Application:
    role(user, "vecino")
    if benefit not in {b["id"] for b in BENEFITS}:
        raise HTTPException(400, "Beneficio inexistente")
    if user.get("preferred_username") not in DEMO_IDENTITIES:
        raise HTTPException(409, "La cuenta no tiene vínculo de prueba con el padrón")
    item = Application(
        id=str(uuid.uuid4()),
        beneficio_id=benefit,
        solicitante_id=user["sub"],
        solicitante_nombre=user.get("preferred_username", ""),
        creada_en=datetime.now(timezone.utc),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def find_application(session: Session, item_id: str) -> Application:
    item = session.get(Application, item_id)
    if not item:
        raise HTTPException(404, "Solicitud inexistente")
    return item


def decide_application(session: Session, user: dict, item_id: str, state: str, reason: str) -> Application:
    role(user, "agente")
    item = find_application(session, item_id)
    if item.estado != "pendiente":
        raise HTTPException(409, "La solicitud ya tiene una decisión")
    if state not in {"aprobada", "rechazada"} or not reason.strip():
        raise HTTPException(400, "Indicá una decisión y un motivo")
    if state == "aprobada":
        identifier = DEMO_IDENTITIES.get(item.solicitante_nombre)
        if not identifier:
            raise HTTPException(409, "No existe vínculo con el padrón")
        try:
            response = httpx.post(f"{PADRON_URL}/verificaciones", json={"identificador": identifier}, timeout=3.0)
        except httpx.RequestError as exc:
            raise HTTPException(503, "No se pudo consultar el padrón; la solicitud sigue pendiente") from exc
        if response.status_code == 503:
            raise HTTPException(503, "El padrón no está disponible; la solicitud sigue pendiente")
        if response.status_code != 200:
            raise HTTPException(503, "El padrón devolvió una respuesta inesperada")
        if response.json().get("condicion") not in {"jubilado", "pensionado"}:
            raise HTTPException(409, "El padrón no confirma la condición requerida")
    item.estado = state
    item.motivo = reason.strip()[:500]
    item.resuelta_en = datetime.now(timezone.utc)
    item.agente_id = user["sub"]
    session.commit()
    session.refresh(item)
    return item


class NewApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    beneficioId: str


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: str
    motivo: str


@app.get("/api/v1/beneficios")
def list_benefits():
    return BENEFITS


@app.post("/api/v1/solicitudes", status_code=201)
def post_application(body: NewApplication, user: dict = Depends(api_user), session: Session = Depends(db_session)):
    item = create_application(session, user, body.beneficioId)
    return JSONResponse(status_code=201, headers={"Location": f"/api/v1/solicitudes/{item.id}"}, content=view_model(item))


@app.get("/api/v1/solicitudes")
def list_applications(estado: str, user: dict = Depends(api_user), session: Session = Depends(db_session)):
    role(user, "agente")
    if estado != "pendiente":
        raise HTTPException(400, "Solo se admite estado=pendiente en este corte")
    return [view_model(item) for item in session.scalars(select(Application).where(Application.estado == estado))]


@app.get("/api/v1/solicitudes/{id}")
def get_application(id: str, user: dict = Depends(api_user), session: Session = Depends(db_session)):
    item = find_application(session, id)
    if "agente" not in user.get("realm_access", {}).get("roles", []) and item.solicitante_id != user["sub"]:
        raise HTTPException(403, "No podés consultar una solicitud ajena")
    return view_model(item)


@app.patch("/api/v1/solicitudes/{id}")
def patch_application(id: str, body: Decision, user: dict = Depends(api_user), session: Session = Depends(db_session)):
    return view_model(decide_application(session, user, id, body.estado, body.motivo))


@app.get("/login")
def login(request: Request):
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    request.session["oidc_state"] = state
    request.session["oidc_verifier"] = verifier
    query = urlencode({"client_id": "municipio-web", "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": "openid profile", "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "login"})
    return RedirectResponse(f"{KC_PUBLIC}/protocol/openid-connect/auth?{query}")


@app.get("/auth/callback")
def callback(request: Request, code: str, state: str):
    if not secrets.compare_digest(state, request.session.get("oidc_state", "")):
        raise HTTPException(400, "Estado de login inválido")
    response = httpx.post(
        f"{KC_INTERNAL}/protocol/openid-connect/token",
        data={"grant_type": "authorization_code", "client_id": "municipio-web", "code": code, "redirect_uri": REDIRECT_URI, "code_verifier": request.session["oidc_verifier"]},
        timeout=10.0,
    )
    if response.status_code != 200:
        raise HTTPException(401, "No se pudo completar el inicio de sesión")
    claims = decode_token(response.json()["access_token"])
    request.session.clear()
    request.session["user"] = {"sub": claims["sub"], "preferred_username": claims.get("preferred_username", ""), "realm_access": claims.get("realm_access", {})}
    request.session["csrf"] = secrets.token_urlsafe(24)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


def web_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Iniciá sesión")
    return user


def check_csrf(request: Request, token: str):
    if not secrets.compare_digest(token, request.session.get("csrf", "")):
        raise HTTPException(403, "Formulario vencido; volvé a cargar la página")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(db_session)):
    user = request.session.get("user")
    items = []
    if user:
        query = select(Application)
        if "agente" in user.get("realm_access", {}).get("roles", []):
            query = query.where(Application.estado == "pendiente")
        else:
            query = query.where(Application.solicitante_id == user["sub"])
        items = list(session.scalars(query.order_by(Application.creada_en.desc())))
    return templates.TemplateResponse(request, "home.html", {"user": user, "items": items, "benefits": BENEFITS, "csrf": request.session.get("csrf", "")})


@app.post("/web/solicitudes")
def web_create(request: Request, beneficio: str = Form(), csrf: str = Form(), session: Session = Depends(db_session)):
    check_csrf(request, csrf)
    item = create_application(session, web_user(request), beneficio)
    return RedirectResponse(f"/web/solicitudes/{item.id}", status_code=303)


@app.get("/web/solicitudes/{item_id}", response_class=HTMLResponse)
def web_detail(item_id: str, request: Request, session: Session = Depends(db_session)):
    user = web_user(request)
    item = find_application(session, item_id)
    if "agente" not in user.get("realm_access", {}).get("roles", []) and item.solicitante_id != user["sub"]:
        raise HTTPException(403, "No podés ver una solicitud ajena")
    return templates.TemplateResponse(request, "detail.html", {"item": item, "user": user, "csrf": request.session.get("csrf", "")})


@app.post("/web/solicitudes/{item_id}/decision")
def web_decide(item_id: str, request: Request, estado: str = Form(), motivo: str = Form(), csrf: str = Form(), session: Session = Depends(db_session)):
    check_csrf(request, csrf)
    decide_application(session, web_user(request), item_id, estado, motivo)
    return RedirectResponse(f"/web/solicitudes/{item_id}", status_code=303)
