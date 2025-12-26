"""LLM Service for interacting with local Ollama instance."""

import logging
import os
from typing import Optional

import ollama  # type: ignore

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with local LLM via Ollama."""

    def __init__(self) -> None:
        """Initialize the LLMService."""
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # Initialize Ollama client
        self.client = ollama.Client(host=self.base_url)
        logger.info(f"LLM Service initialized with model: {self.model}")

    def check_health(self) -> bool:
        """Check if the LLM service is reachable."""
        try:
            self.client.list()
            return True
        except Exception as e:
            logger.warning(f"LLM Service health check failed: {e}")
            return False

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM."""
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"

            messages.append({"role": "user", "content": full_prompt})

            response = self.client.chat(
                model=self.model,
                messages=messages,
            )

            return str(response["message"]["content"])

        except Exception as e:
            logger.error(f"Failed to generate LLM response: {e}")
            # Return a friendly error message instead of crashing
            return (
                "I apologize, but I'm currently unable to connect to my AI brain "
                "(Ollama). Please ensure the Ollama service is running."
            )
