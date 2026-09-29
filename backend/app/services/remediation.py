from pathlib import Path

from app.services.repository import (
    get_repository_file,
    update_repository_file,
)


class RemediationService:

    def validate_fix(self, proposed_fix: dict):
        if proposed_fix.get("type") == "none":
            return False, "No executable fix was proposed"

        if proposed_fix.get("requiresApproval") is not True:
            return False, "Fix must require human approval"

        target_file = proposed_fix.get("targetFile")

        if not target_file:
            return False, "No target file specified"

        if target_file.startswith("/"):
            return False, "Absolute file paths are not allowed"

        target_path = Path(target_file)

        if ".." in target_path.parts:
            return False, "Parent-directory traversal is not allowed"

        changes = proposed_fix.get("changes", [])

        if not changes:
            return False, "No changes were specified"

        return True, "Fix is valid"

    def execute(
        self,
        proposed_fix: dict,
        repository_url: str,
        github_token: str,
    ):
        valid, message = self.validate_fix(
            proposed_fix
        )

        if not valid:
            return {
                "executed": False,
                "message": message
            }

        target_file = proposed_fix["targetFile"]

        # Read the current file before modifying it.
        current_file = get_repository_file(
            repository_url=repository_url,
            github_token=github_token,
            file_path=target_file,
        )

        current_content = current_file["content"]

        # The proposed changes must explicitly provide
        # the complete new file content.
        new_content = proposed_fix.get("newContent")

        if new_content is None:
            return {
                "executed": False,
                "message": (
                    "Fix was approved and the target file "
                    "was read, but no exact newContent was "
                    "provided. Repository modification was "
                    "not performed."
                ),
                "targetFile": target_file,
                "currentContentLength": len(current_content),
            }

        if not isinstance(new_content, str):
            return {
                "executed": False,
                "message": "newContent must be a string"
            }

        if new_content == current_content:
            return {
                "executed": False,
                "message": (
                    "The proposed content is identical to "
                    "the current repository file."
                ),
                "targetFile": target_file,
            }

        result = update_repository_file(
            repository_url=repository_url,
            github_token=github_token,
            file_path=target_file,
            content=new_content,
            commit_message=(
                "chore: apply approved incident remediation"
            ),
        )

        return {
            "executed": True,
            "message": (
                "Approved remediation was applied "
                "successfully."
            ),
            "targetFile": target_file,
            "commit": result.get("commit"),
            "branch": result.get("branch"),
        }