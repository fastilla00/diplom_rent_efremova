# EcomProfit Guard — forecast router
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.forecast import ForecastRequest, ForecastResponse, PredictionPoint
from app.services.forecast_ml import run_forecast
from app.routers.auth import require_user

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.post("/{project_id}", response_model=ForecastResponse)
async def create_forecast(
    project_id: int,
    body: ForecastRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> ForecastResponse:
    """Прогноз рентабельности по выбранной модели и горизонту (см. `ForecastRequest`)."""
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    allowed = (
        "arima",
        "sarimax",
        "catboost",
        "lightgbm",
        "prophet",
        "rnn",
        "ensemble",
        "auto",
    )
    if body.model_type not in allowed:
        raise HTTPException(
            400,
            "model_type must be one of: " + ", ".join(allowed),
        )
    result = await run_forecast(db, project_id, body.horizon_months, body.model_type)
    preds = [PredictionPoint(**p) for p in result.get("predictions", [])]
    return ForecastResponse(
        model=result.get("model", "naive"),
        predictions=preds,
        metrics=jsonable_encoder(result.get("metrics", {})),
        note=result.get("note"),
    )
