from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware import BasicAuthMiddlewareDocs, HostWhitelistMiddleware
from dotenv import load_dotenv
import uvicorn
import json
import os
from configs.db import Base, engine
from models.klaimBpjs import KlaimBpjs

load_dotenv(override=True)
PORT_FASTAPI = os.getenv("PORT_FASTAPI")
ALLOWED_CORS = os.getenv("ALLOWED_CORS")
LIST_CORS = json.loads(ALLOWED_CORS) if ALLOWED_CORS else ["*"]


# conect to the database
Base.metadata.create_all(bind=engine)
print("Registered tables:", Base.metadata.tables.keys())
print("Database URL:", engine.url)


app = FastAPI(title='Endpoint Service AI Checking Document Klaim Paperless Hospital', version='13.3')

app.add_middleware(BasicAuthMiddlewareDocs)
app.add_middleware(HostWhitelistMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=LIST_CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom RAG Router (for comparison)
from routers.rag_engine import router as rag_engine_router
app.include_router(rag_engine_router, prefix='/checking-klaim-bpjs/v1')

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(PORT_FASTAPI),
        log_level="info",
        # forwarded_allow_ips="*",
        reload=True,
        reload_excludes="*.log",
        reload_dirs=["configs", "models", "routers", "schemas", "services", "utils"],
        reload_includes="*.py"
    )
