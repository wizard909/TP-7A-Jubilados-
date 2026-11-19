import json
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./municipio.db")
PADRON_URL = os.environ.get("PADRON_URL", "http://localhost:8090")
KC_PUBLIC = os.environ.get("KEYCLOAK_PUBLIC", "http://localhost:8180/realms/municipio")
KC_INTERNAL = os.environ.get("KEYCLOAK_INTERNAL", KC_PUBLIC)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "solo-desarrollo-local")
DEMO_IDENTITIES = json.loads(os.environ.get("DEMO_IDENTITIES", '{"vecino1":"JUB-001","vecino2":"NO-003"}'))
APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "http://localhost:8080").rstrip("/")
REDIRECT_URI = APP_PUBLIC_URL + "/auth/callback"
