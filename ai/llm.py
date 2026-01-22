"""Module for interacting with the local LLM service."""

import logging
import os
from typing import Optional

import ollama  # type: ignore
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with local LLM via Ollama."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize the LLMService with configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.model = self.config["llm"]["model"]
        self.base_url = self.config["llm"]["base_url"]

        # Initialize Ollama client
        self.client = ollama.Client(host=self.base_url)
        logger.info(f"LLM Service initialized with model: {self.model}")

    def check_health(self) -> bool:
        """Check if the LLM service is reachable."""
        try:
            self.client.list()
            return True
        except Exception:
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

            # Extract options from config with type safety
            temperature = float(self.config["llm"].get("temperature", 0.7))
            context_window = int(self.config["llm"].get("context_window", 4096))

            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_ctx": context_window,
                },
            )

            return str(response["message"]["content"])

        except Exception as e:
            logger.error(f"Failed to generate LLM response: {e}")
            return (
                "I apologize, but I'm currently unable to connect to my AI brain "
                "(Ollama). Please ensure the Ollama service is running."
            )
