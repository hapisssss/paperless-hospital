from fastapi import HTTPException, status
from fastapi.security import HTTPBasic
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from configs.config import USERNAME_DOCS_SWAGGER, PASSWORD_DOCS_SWAGGER
import secrets
import base64
import binascii
from dotenv import load_dotenv
import json
import os

load_dotenv(override=True)

try:
    WHITELIST_HOST = json.loads(os.getenv("WHITELIST_HOSTS", "[]"))
except json.JSONDecodeError:
    WHITELIST_HOST = []

security = HTTPBasic()

# Middleware untuk Basic Auth
class BasicAuthMiddlewareDocs(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            auth = request.headers.get("Authorization")
            if not auth:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Not authenticated", "messege": "Not authenticated"},
                    headers={"WWW-Authenticate": "Basic"},
                )
            try:
                scheme, credentials = auth.split()
                if scheme.lower() != "basic":
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail":"Invalid authentication scheme", "messege": "Invalid authentication scheme"},
                        headers={"WWW-Authenticate": "Basic"},
                    )
                decoded_credentials = base64.b64decode(credentials).decode("utf-8")
                username, password = decoded_credentials.split(":")
                if not (secrets.compare_digest(username, USERNAME_DOCS_SWAGGER) and secrets.compare_digest(password, PASSWORD_DOCS_SWAGGER)):
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail":"Invalid username or password", "messege": "Invalid username or password"},
                        headers={"WWW-Authenticate": "Basic"},
                    )
            except (ValueError, UnicodeDecodeError, binascii.Error):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail":"Invalid credentials", "messege": "Invalid credentials"},
                    headers={"WWW-Authenticate": "Basic"},
                )
        response = await call_next(request)
        return response
    
class HostWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_host = request.headers.get("host", "").split(":")[0] 

        if request_host not in WHITELIST_HOST:
            return JSONResponse(status_code=403, content={"detail": f"Access denied 🙅🤪"})

        return await call_next(request)