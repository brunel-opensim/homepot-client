"""LLM provider abstraction for multi-backend support.

Supports Ollama (local), OpenAI, and Anthropic.  The active provider is
selected via ``llm.provider`` in config.yaml.  External providers require
API keys from environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY).

Usage:
    from ai.llm_providers import create_llm_provider
    provider = create_llm_provider(config)
    response = provider.generate_response(prompt="...", context="...", system_prompt="...")
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMProvider:
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the provider with configuration."""
        self.config = config
        self.llm_config = config.get("llm", {})

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM."""
        raise NotImplementedError

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> Any:
        """Generate a response with tool calling support."""
        raise NotImplementedError

    def check_health(self) -> bool:
        """Check if the LLM service is reachable."""
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    """Local Ollama provider."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Ollama provider."""
        super().__init__(config)
        import ollama  # type: ignore

        self.model = self.llm_config.get("model", "llama3.2")
        self.base_url = self.llm_config.get("base_url", "http://localhost:11434")
        self.keep_alive = self.llm_config.get("keep_alive", "30m")
        self.client = ollama.Client(host=self.base_url)
        logger.info("Ollama provider initialized with model: %s", self.model)

    def check_health(self) -> bool:
        """Check if Ollama is reachable."""
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
        """Generate a response via Ollama."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
            messages.append({"role": "user", "content": full_prompt})

            temperature = float(self.llm_config.get("temperature", 0.7))
            context_window = int(self.llm_config.get("context_window", 4096))
            options = {
                "temperature": temperature,
                "num_ctx": context_window,
            }
            num_predict = self.llm_config.get("num_predict")
            if num_predict:
                options["num_predict"] = int(num_predict)

            response = self.client.chat(
                model=self.model,
                messages=messages,
                options=options,
                keep_alive=self.keep_alive,
            )

            content = str(response["message"]["content"])
            done_reason = response.get("done_reason")
            if done_reason == "length":
                content = content.rstrip() + " …"
            return content

        except Exception as e:
            logger.error("Ollama generate failed: %s", e)
            return (
                "I apologize, but I'm currently unable to connect to my AI brain "
                "(Ollama). Please ensure the Ollama service is running."
            )

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> Any:
        """Generate a response with tool calling via Ollama."""
        import ollama  # type: ignore

        temperature = float(self.llm_config.get("temperature", 0.7))
        context_window = int(self.llm_config.get("context_window", 4096))
        options = {
            "temperature": temperature,
            "num_ctx": context_window,
        }
        num_predict = self.llm_config.get("num_predict")
        if num_predict:
            options["num_predict"] = int(num_predict)

        try:
            return self.client.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                options=options,
                keep_alive=self.keep_alive,
            )
        except Exception as e:
            logger.error("Ollama generate_with_tools failed: %s", e)
            return ollama.ChatResponse(
                message=ollama.Message(
                    content=(
                        "I apologize, but I'm currently unable to connect to my AI brain "
                        "(Ollama). Please ensure the Ollama service is running."
                    ),
                    role="assistant",
                )
            )


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4o, GPT-4o-mini, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the OpenAI provider."""
        super().__init__(config)
        import openai

        ext = self.llm_config.get("external", {}).get("openai", {})
        self.model = ext.get("model", "gpt-4o-mini")
        api_key = os.environ.get(ext.get("api_key_env", "OPENAI_API_KEY"), "")
        if not api_key:
            from .provider import get_api_key

            api_key = get_api_key("openai") or ""
        base_url = ext.get("base_url", "https://api.openai.com/v1")
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.temperature = float(self.llm_config.get("temperature", 0.7))
        self.max_tokens = int(
            ext.get("num_predict", self.llm_config.get("num_predict", 160))
        )
        logger.info("OpenAI provider initialized with model: %s", self.model)

    def check_health(self) -> bool:
        """Check if OpenAI API is reachable."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response via Ollama."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
            messages.append({"role": "user", "content": full_prompt})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI generate failed: %s", e)
            return f"AI error (OpenAI): {e}"

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> Any:
        """Generate a response with tool calling via OpenAI."""
        # Convert tools to OpenAI format if needed
        oai_tools = []
        for t in tools:
            if isinstance(t, dict) and "function" in t:
                oai_tools.append(t)
            else:
                oai_tools.append({"type": "function", "function": t})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                tools=oai_tools if oai_tools else None,  # type: ignore[arg-type]
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            # Wrap in a compatible object
            msg = response.choices[0].message
            tool_calls = None
            if msg.tool_calls:
                tool_calls = [
                    {
                        "function": {
                            "name": tc.function.name,  # type: ignore[union-attr]
                            "arguments": tc.function.arguments,  # type: ignore[union-attr]
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return _ToolResponse(content=msg.content or "", tool_calls=tool_calls)
        except Exception as e:
            logger.error("OpenAI generate_with_tools failed: %s", e)
            return _ToolResponse(content=f"AI error (OpenAI): {e}", tool_calls=None)


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude 3.5 Sonnet/Haiku, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the Anthropic provider."""
        super().__init__(config)
        import anthropic

        ext = self.llm_config.get("external", {}).get("anthropic", {})
        self.model = ext.get("model", "claude-haiku-4-5-20251001")
        api_key = os.environ.get(ext.get("api_key_env", "ANTHROPIC_API_KEY"), "")
        if not api_key:
            from .provider import get_api_key

            api_key = get_api_key("anthropic") or ""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_tokens = int(
            ext.get("num_predict", self.llm_config.get("num_predict", 160))
        )
        logger.info("Anthropic provider initialized with model: %s", self.model)

    def check_health(self) -> bool:
        """Check if Anthropic API is reachable."""
        try:
            # Anthropic doesn't have a simple health check; try a minimal call
            self.client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False

    def generate_response(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response via Anthropic."""
        try:
            full_prompt = prompt
            if context:
                full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"

            kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": full_prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = self.client.messages.create(**kwargs)
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error("Anthropic generate failed: %s", e)
            return f"AI error (Anthropic): {e}"

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
    ) -> Any:
        """Generate a response with tool calling via Anthropic."""
        # Convert tools to Anthropic format
        ant_tools = []
        for t in tools:
            if isinstance(t, dict) and "function" in t:
                fn = t["function"]
                ant_tools.append(
                    {
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {}),
                    }
                )
            else:
                ant_tools.append(t)

        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
                "tools": ant_tools if ant_tools else None,
            }
            # Extract system message if present
            system_msg = None
            filtered_msgs = []
            for m in messages:
                if m.get("role") == "system":
                    system_msg = m.get("content", "")
                else:
                    filtered_msgs.append(m)
            if system_msg:
                kwargs["messages"] = filtered_msgs
                kwargs["system"] = system_msg

            response = self.client.messages.create(**kwargs)
            # Extract tool calls
            tool_calls = None
            for block in response.content:
                if block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(
                        {
                            "function": {
                                "name": block.name,
                                "arguments": block.input,
                            }
                        }
                    )
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
            return _ToolResponse(content=text_content, tool_calls=tool_calls)
        except Exception as e:
            logger.error("Anthropic generate_with_tools failed: %s", e)
            return _ToolResponse(content=f"AI error (Anthropic): {e}", tool_calls=None)


class _ToolResponse:
    """Lightweight wrapper to normalize tool-calling responses across providers."""

    def __init__(self, content: str, tool_calls: Optional[list] = None) -> None:
        """Initialize the tool response wrapper."""
        self.content = content
        self.tool_calls = tool_calls
        self.message = self

    @property
    def tool_calls_list(self) -> Optional[list]:
        return self.tool_calls


def create_llm_provider(config: Dict[str, Any]) -> "LLMProvider":
    """Create the appropriate LLM provider based on config.

    Args:
        config: Full config dict (from config.yaml or agent config).

    Returns:
        An LLMProvider instance.

    Provider selection:
        - "ollama" (default): Local Ollama
        - "openai": OpenAI API
        - "anthropic": Anthropic API
    """
    provider_name = config.get("llm", {}).get("provider", "ollama").lower()
    if provider_name == "openai":
        return OpenAIProvider(config)
    elif provider_name == "anthropic":
        return AnthropicProvider(config)
    else:
        return OllamaProvider(config)
