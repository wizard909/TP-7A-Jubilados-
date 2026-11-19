import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from jwt import PyJWKClient

from .configuracion import APP_PUBLIC_URL, KC_INTERNAL, KC_PUBLIC, REDIRECT_URI, SESSION_SECRET
from .solicitudes.servicio import Actor

router = APIRouter()
jwks = PyJWKClient(f"{KC_INTERNAL}/protocol/openid-connect/certs")

# SessionMiddleware signs cookies. Encrypt the OIDC logout hint before storing it.
logout_cipher = Fernet(base64.urlsafe_b64encode(
    hashlib.sha256(b"municipio-logout\0" + SESSION_SECRET.encode()).digest()
))


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


def actor_from_claims(user: dict) -> Actor:
    return Actor(user['sub'], user.get('preferred_username', ''),
                 frozenset(user.get('realm_access', {}).get('roles', [])))


@router.get("/login")
def login(request: Request):
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    request.session["oidc_state"] = state
    request.session["oidc_verifier"] = verifier
    query = urlencode({"client_id": "municipio-web", "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": "openid profile", "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "login"})
    return RedirectResponse(f"{KC_PUBLIC}/protocol/openid-connect/auth?{query}")


@router.get("/auth/callback")
def callback(request: Request, code: str, state: str):
    expected_state = request.session.get("oidc_state")
    verifier = request.session.get("oidc_verifier")
    if not expected_state or not verifier or not secrets.compare_digest(state, expected_state):
        raise HTTPException(400, "Estado de login inválido")
    response = httpx.post(
        f"{KC_INTERNAL}/protocol/openid-connect/token",
        data={"grant_type": "authorization_code", "client_id": "municipio-web", "code": code, "redirect_uri": REDIRECT_URI, "code_verifier": verifier},
        timeout=10.0,
    )
    if response.status_code != 200:
        raise HTTPException(401, "No se pudo completar el inicio de sesión")
    tokens = response.json()
    claims = decode_token(tokens["access_token"])
    request.session.clear()
    request.session["user"] = {"sub": claims["sub"], "preferred_username": claims.get("preferred_username", ""), "realm_access": claims.get("realm_access", {})}
    request.session["csrf"] = secrets.token_urlsafe(24)
    if id_token := tokens.get("id_token"):
        request.session["logout_hint"] = logout_cipher.encrypt(id_token.encode()).decode()
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    user = request.session.get("user")
    stored_hint = request.session.get("logout_hint")
    request.session.clear()
    if not user:
        return RedirectResponse("/", status_code=303)

    params = {"client_id": "municipio-web", "post_logout_redirect_uri": APP_PUBLIC_URL + "/"}
    if stored_hint:
        try:
            params["id_token_hint"] = logout_cipher.decrypt(stored_hint.encode()).decode()
        except InvalidToken:
            pass  # Keycloak can ask for confirmation if the hint is unavailable.
    return RedirectResponse(
        f"{KC_PUBLIC}/protocol/openid-connect/logout?{urlencode(params)}",
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def web_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Iniciá sesión")
    return user


def check_csrf(request: Request, token: str):
    if not secrets.compare_digest(token, request.session.get("csrf", "")):
        raise HTTPException(403, "Formulario vencido; volvé a cargar la página")
