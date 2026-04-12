# EcomProfit Guard — FastAPI application
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, projects, sync, dashboard, analytics, alerts, forecast, app_config
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # shutdown if needed


app = FastAPI(
    title="EcomProfit Guard",
    description="Анализ и прогнозирование рентабельности проектов",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api")
app.include_router(app_config.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")


@app.get("/")
def root():
    return {"app": "EcomProfit Guard", "docs": "/docs"}
