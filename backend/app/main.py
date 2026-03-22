from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="AiWriter API",
        version="0.1.0",
        description="AI Novel Writing System",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": str(exc.status_code),
                    "message": exc.detail,
                    "details": None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "500",
                    "message": "Internal server error",
                    "details": None,
                }
            },
        )

    # Register routers
    from app.api.projects import router as projects_router
    from app.api.volumes import router as volumes_router
    from app.api.chapters import router as chapters_router
    from app.api.entities import router as entities_router

    app.include_router(projects_router)
    app.include_router(volumes_router)
    app.include_router(chapters_router)
    app.include_router(entities_router)

    from app.api.pipeline import router as pipeline_router
    from app.api.truth_files import router as truth_files_router

    app.include_router(pipeline_router)
    app.include_router(truth_files_router)

    return app


app = create_app()


@app.get("/health")
async def health():
    return {"status": "ok"}
