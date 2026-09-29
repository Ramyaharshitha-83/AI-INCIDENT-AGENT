from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.remediation import RemediationService


router = APIRouter(
    prefix="/api/remediation",
    tags=["Remediation"]
)


remediation_service = RemediationService()


class ProposedFix(BaseModel):
    type: str
    targetFile: str
    description: str
    changes: list[str]
    requiresApproval: bool
    newContent: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    proposedFix: ProposedFix


@router.post("/approve")
def approve_remediation(
    approval: ApprovalRequest,
    request: Request,
):
    proposed_fix = approval.proposedFix

    if not approval.approved:
        return {
            "success": True,
            "approved": False,
            "executed": False,
            "message": "Remediation rejected by user"
        }

    if not proposed_fix.requiresApproval:
        raise HTTPException(
            status_code=400,
            detail="Proposed fix must require human approval"
        )

    if proposed_fix.type == "none":
        return {
            "success": True,
            "approved": True,
            "executed": False,
            "message": "No executable fix was proposed"
        }

    if not proposed_fix.targetFile:
        raise HTTPException(
            status_code=400,
            detail="Proposed fix has no target file"
        )

    repository_url = request.headers.get(
        "X-Repository-URL"
    )

    github_token = request.cookies.get(
        "github_session"
    )

    if not repository_url:
        raise HTTPException(
            status_code=400,
            detail="Repository URL is required"
        )

    if not github_token:
        raise HTTPException(
            status_code=401,
            detail="GitHub session not found"
        )

    execution = remediation_service.execute(
        proposed_fix.model_dump(),
        repository_url,
        github_token,
    )

    return {
        "success": True,
        "approved": True,
        "executed": execution["executed"],
        "message": execution["message"],
        "proposedFix": proposed_fix.model_dump(),
        "execution": execution,
    }