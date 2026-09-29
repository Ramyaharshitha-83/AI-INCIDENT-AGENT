import json

from app.services.hindsight import HindsightService
from app.services.llm import LLMService
from app.services.applications import get_application
from app.models.incident import IncidentAnalysisRequest

from app.services.repository_context import (
    get_relevant_repository_context,
)

class IncidentAnalysisService:

    def __init__(self):
        self.hindsight = HindsightService()
        self.llm = LLMService()

    def analyze(
        self,
        incident: IncidentAnalysisRequest,
        user_id: int,
        github_token: str,
    ):

        application = get_application(
            application_id=incident.application_id,
            user_id=user_id,
        )

        if not application:
            raise ValueError(
                "Application not found or does not belong to the current user"
            )

        connection_utilization = (
            incident.dbConnections /
            incident.dbConnectionLimit
        ) * 100

        current_incident = {
            "applicationId": incident.application_id,
            "service": incident.service,
            "latencyMs": incident.latencyMs,
            "errorRate": incident.errorRate,
            "dbConnections": incident.dbConnections,
            "dbConnectionLimit": incident.dbConnectionLimit,
            "dbConnectionUtilization": round(
                connection_utilization,
                2
            ),
            "cpu": incident.cpu,
            "memory": incident.memory
        }

        # ----------------------------------------------------
        # Hindsight historical experience
        # ----------------------------------------------------

        query = (
            f"{incident.service} "
            f"high latency {incident.latencyMs} ms "
            f"high error rate {incident.errorRate}% "
            f"database connections {incident.dbConnections} "
            f"connection utilization "
            f"{connection_utilization:.1f}%"
        )

        historical_memory = self.hindsight.recall(
            query
        )

        # ----------------------------------------------------
        # Repository context
        # ----------------------------------------------------

        repository_context = None

        source_type = application.get(
            "source_type"
        )

        repository_url = application.get(
            "source_url"
        )

        if (
            source_type == "GitHub"
            and repository_url
            and github_token
        ):

            repository_context = (
                get_relevant_repository_context(
                    repository_url=repository_url,
                    github_token=github_token,
                    service_name=incident.service,
                    incident=incident,
                )
            )

        # ----------------------------------------------------
        # LLM instructions
        # ----------------------------------------------------

        system_prompt = """
You are an AI Site Reliability Engineering incident-response agent.

Your job is to analyze a CURRENT production incident using:

1. Current telemetry
2. The application's actual repository source/configuration
3. Historical experiences retrieved from Hindsight

IMPORTANT RULES:

- Analyze the current telemetry independently first.
- Inspect the repository evidence before identifying a
  repository component as a root cause.
- Do not assume that a telemetry field proves that the
  corresponding technology exists in the application.
- Do not diagnose a database problem unless repository
  evidence or explicit external-system evidence supports
  a database dependency.
- Do not identify an affected file based only on its filename.
- Affected files must contain actual code or configuration
  evidence relevant to the incident.
- Treat Hindsight memories as organizational experience and
  supporting evidence, not guaranteed truth.
- Do not blindly copy historical conclusions.
- If historical experience conflicts with current telemetry,
  prioritize current telemetry.
- Clearly distinguish confirmed evidence from hypotheses.
- Do not invent repository code, incidents, dependencies,
  or historical facts.
- If repository evidence cannot explain the incident,
  explicitly state that external evidence is required.
- Any remediation action requires human approval.

Return ONLY valid JSON.

Use exactly this structure:

{
  "diagnosis": {
    "rootCause": "string",
    "confidence": 0.0
  },
  "reasoning": "string",
  "evidence": [
    "string"
  ],
  "repositoryEvidence": [
    {
      "file": "string",
      "evidence": "string"
    }
  ],
  "historicalContext": {
    "relevant": true,
    "reason": "string",
    "incidents": [
      "string"
    ]
  },
  "recommendation": {
    "action": "string",
    "reason": "string",
    "requiresApproval": true
  }
}

The confidence value must be between 0 and 1.
"""

        user_prompt = f"""
CURRENT INCIDENT:

{json.dumps(current_incident, indent=2)}

APPLICATION:

{json.dumps(application, indent=2)}

REPOSITORY CONTEXT:

{json.dumps(repository_context, indent=2)}

HISTORICAL EXPERIENCE FROM HINDSIGHT:

{json.dumps(historical_memory, indent=2)}

Analyze the incident.

First reason from the current telemetry.

Then inspect the actual repository evidence.

Then determine whether the historical experience is
relevant to the current conditions.

Do not assume a component exists merely because the
telemetry contains a metric for it.

Identify confirmed evidence separately from hypotheses.

Finally provide the diagnosis and recommended next action.
"""

        # ----------------------------------------------------
        # LLM analysis
        # ----------------------------------------------------

        llm_response = self.llm.analyze(
            system_prompt,
            user_prompt
        )

        try:

            ai_analysis = json.loads(
                llm_response
            )

        except json.JSONDecodeError:

            ai_analysis = {
                "rawAnalysis": llm_response
            }

        # ----------------------------------------------------
        # Final response
        # ----------------------------------------------------

        return {
            "incident": current_incident,
            "application": application,
            "repositoryContext": repository_context,
            "hindsightQuery": query,
            "historicalExperience": historical_memory,
            "aiAnalysis": ai_analysis
        }