"""Module for interacting with the local LLM service.

This module now delegates to the provider abstraction in ``ai.llm_providers``,
which supports Ollama (local), OpenAI, and Anthropic.  The active provider is
selected via ``llm.provider`` in config.yaml.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import yaml

from .llm_providers import create_llm_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with an LLM via the configured provider.

    Delegates all calls to the underlying provider (Ollama, OpenAI, or
    Anthropic).  The provider is selected from ``config.yaml``:
    ``llm.provider`` = "ollama" | "openai" | "anthropic".
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the LLMService with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.provider = create_llm_provider(self.config)
        self.model = (
            self.provider.model if hasattr(self.provider, "model") else "unknown"
        )
        self.base_url = getattr(self.provider, "base_url", "")
        self.keep_alive = self.config.get("llm", {}).get("keep_alive", "30m")

        logger.info(
            "LLM Service initialized with provider: %s, model: %s",
            self.config.get("llm", {}).get("provider", "ollama"),
            self.model,
        )

    def check_health(self) -> bool:
        """Check if the LLM service is reachable."""
        return self.provider.check_health()

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM."""
        return self.provider.generate_response(
            prompt=prompt, context=context, system_prompt=system_prompt
        )

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> Any:
        """Generate a response with tool calling support."""
        return self.provider.generate_with_tools(messages=messages, tools=tools)
