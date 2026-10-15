"""Module for interacting with the local LLM service."""

import logging
import os
from typing import Any, Dict, List, Optional

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
        # How long Ollama keeps the model loaded after a request. A long value
        # avoids paying the (tens of seconds) cold-load cost on sparse queries.
        self.keep_alive = self.config["llm"].get("keep_alive", "30m")

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
            options = {
                "temperature": temperature,
                "num_ctx": context_window,
            }
            num_predict = self.config["llm"].get("num_predict")
            if num_predict:
                options["num_predict"] = int(num_predict)

            response = self.client.chat(
                model=self.model,
                messages=messages,
                options=options,
                keep_alive=self.keep_alive,
            )

            def _ms(ns: Any) -> float:
                try:
                    return round(float(ns) / 1e6, 1)
                except (TypeError, ValueError):
                    return -1.0

            # Per-request timing breakdown from Ollama: how much of the time is
            # prompt evaluation (context/prefix) vs token generation. Essential
            # for diagnosing slow answers on CPU-only hosts (see docs).
            # done_reason == "length" means we hit num_predict and the answer was
            # truncated (a deliberate latency bound, not an error).
            done_reason = response.get("done_reason")
            logger.info(
                "LLM generate | system_chars=%d prompt_chars=%d num_ctx=%d "
                "num_predict=%s | prompt_eval_count=%s prompt_eval_ms=%s "
                "eval_count=%s eval_ms=%s load_ms=%s total_ms=%s done_reason=%s",
                len(system_prompt or ""),
                len(full_prompt),
                context_window,
                options.get("num_predict"),
                response.get("prompt_eval_count"),
                _ms(response.get("prompt_eval_duration")),
                response.get("eval_count"),
                _ms(response.get("eval_duration")),
                _ms(response.get("load_duration")),
                _ms(response.get("total_duration")),
                done_reason,
            )

            content = str(response["message"]["content"])
            if done_reason == "length":
                content = content.rstrip() + " …"
            return content

        except Exception as e:
            logger.error(f"Failed to generate LLM response: {e}")
            return (
                "I apologize, but I'm currently unable to connect to my AI brain "
                "(Ollama). Please ensure the Ollama service is running."
            )

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> ollama.ChatResponse:
        """Generate a response with tool calling support.

        Args:
            messages: Full message history (system, user, assistant, tool).
            tools: List of tool functions or JSON schema dicts for Ollama.

        Returns:
            ChatResponse with .message.content and .message.tool_calls.
        """
        try:
            temperature = float(self.config["llm"].get("temperature", 0.7))
            context_window = int(self.config["llm"].get("context_window", 4096))
            options = {
                "temperature": temperature,
                "num_ctx": context_window,
            }
            num_predict = self.config["llm"].get("num_predict")
            if num_predict:
                options["num_predict"] = int(num_predict)

            response = self.client.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                options=options,
                keep_alive=self.keep_alive,
            )

            return response

        except Exception as e:
            logger.error("Failed to generate LLM response with tools: %s", e)
            # Return a mock response that signals failure
            return ollama.ChatResponse(
                message=ollama.Message(
                    content=(
                        "I apologize, but I'm currently unable to connect to my AI brain "
                        "(Ollama). Please ensure the Ollama service is running."
                    ),
                    role="assistant",
                )
            )
