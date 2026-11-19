from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import api, seguridad, web
from .configuracion import SESSION_SECRET
from .errores_http import instalar_manejadores
from .persistencia import engine
from .solicitudes.repositorio import SolicitudRow


@asynccontextmanager
async def lifespan(app: FastAPI):
    SolicitudRow.metadata.create_all(engine)
    yield


app = FastAPI(title="Beneficios municipales", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(api.router)
app.include_router(seguridad.router)
app.include_router(web.router)
instalar_manejadores(app, web.templates)
