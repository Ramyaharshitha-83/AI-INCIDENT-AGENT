from fastapi import APIRouter, HTTPException, Request

from app.models.incident import IncidentAnalysisRequest
from app.services.incident_analysis import IncidentAnalysisService
from app.services.auth import get_current_user


router = APIRouter(
    prefix="/api/incidents",
    tags=["Incidents"]
)

analysis_service = IncidentAnalysisService()


@router.post("/analyze")
def analyze_incident(
    incident: IncidentAnalysisRequest,
    request: Request,
):
    user = get_current_user(request)

    github_token = request.cookies.get(
        "github_session"
    )

    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="GitHub session not found"
        )

    try:
        return analysis_service.analyze(
            incident,
            user["id"],
            github_token,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )