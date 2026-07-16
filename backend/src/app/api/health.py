from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

router = APIRouter()


class HealthReport(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/api/health", response_model=HealthReport)
async def health(request: Request, response: Response) -> HealthReport:
    database_ok = await request.app.state.database.ping()
    if not database_ok:
        response.status_code = 503
    return HealthReport(
        status="ok" if database_ok else "degraded",
        checks={"database": "ok" if database_ok else "error"},
    )
