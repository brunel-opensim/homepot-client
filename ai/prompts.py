"""Prompt templates and formatting logic for the AI service."""

from typing import Any, Dict, List


class PromptManager:
    """Manages prompt construction and templates."""

    @staticmethod
    def build_live_context(
        device_id: str | None,
        prediction: Dict[str, Any] | None,
        risk_factors: List[str] | None,
        recent_events: List[Any] | None,
        context_data: Dict[str, str],
    ) -> str:
        """Construct the live context section of the prompt."""
        # Unpack context data with defaults
        job_ctx = context_data.get("job", "")
        error_ctx = context_data.get("error", "")
        config_ctx = context_data.get("config", "")
        audit_ctx = context_data.get("audit", "")
        api_ctx = context_data.get("api", "")
        state_ctx = context_data.get("state", "")
        push_ctx = context_data.get("push", "")
        site_ctx = context_data.get("site", "")
        meta_ctx = context_data.get("metadata", "")
        user_ctx = context_data.get("user", "")
        metrics_ctx = context_data.get("metrics", "")
        alert_ctx = context_data.get("alert", "")

        if not device_id:
            # Global/Dashboard View Context
            return (
                f"\n[CURRENT SYSTEM STATUS]\n"
                f"\n{alert_ctx}\n\n"
                f"{api_ctx}\n"
                f"----------------------------------------\n"
            )

        # Device-Specific View Context
        return (
            f"\n[CURRENT SYSTEM STATUS]\n"
            f"Device ID: {device_id}\n"
            f"Risk Level: {prediction.get('risk_level', 'UNKNOWN') if prediction else 'UNKNOWN'}\n"
            f"Failure Probability: {prediction.get('failure_probability', 0.0) if prediction else 0.0}\n"
            f"Risk Factors: {', '.join(risk_factors or [])}\n"
            f"Recent Events: {recent_events}\n"
            f"\n{alert_ctx}\n\n"
            f"{job_ctx}\n"
            f"{error_ctx}\n"
            f"{config_ctx}\n"
            f"{audit_ctx}\n"
            f"{api_ctx}\n"
            f"{state_ctx}\n"
            f"{push_ctx}\n"
            f"{site_ctx}\n"
            f"{meta_ctx}\n"
            f"{user_ctx}\n"
            f"{metrics_ctx}\n"
            f"----------------------------------------\n"
        )

    @staticmethod
    def build_full_prompt(
        live_context: str, long_term_context: str, short_term_context: str
    ) -> str:
        """Combine all context layers into the final prompt."""
        return (
            f"{live_context}\n"
            f"Relevant History:\n{long_term_context}\n\n"
            f"Current Conversation:\n{short_term_context}"
        )
