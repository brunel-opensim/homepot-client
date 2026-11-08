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
from typing import Any, Callable, Dict, List, Optional, cast
import uuid

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
        self.keep_alive = self.llm_config.get("keep_alive", "24h")
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
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=_openai_messages(messages),  # type: ignore[arg-type]
                tools=_openai_tools(tools) or None,  # type: ignore[arg-type]
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            msg = response.choices[0].message
            tool_calls = None
            if msg.tool_calls:
                tool_calls = [
                    _ToolCall(
                        name=tc.function.name,  # type: ignore[union-attr]
                        arguments=tc.function.arguments,  # type: ignore[union-attr]
                        call_id=getattr(tc, "id", None),
                    )
                    for tc in msg.tool_calls
                ]
            return _ToolResponse(content=msg.content or "", tool_calls=tool_calls)
        except Exception as e:
            logger.error("OpenAI generate_with_tools failed: %s", e)
            return _ToolResponse(content=f"AI error (OpenAI): {e}", tool_calls=None)

    def generate_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Any:
        """Generate a tool-calling response via OpenAI, streaming text deltas.

        Tool-call arguments arrive as fragments across chunks, so they are
        accumulated by tool-call index and re-assembled into the same normalized
        ``_ToolResponse`` shape as :meth:`generate_with_tools`.
        """
        try:
            # The sync OpenAI client types a streaming response as a union of
            # chunk and tuple, so annotate as Any and read fields defensively.
            stream: Any = self.client.chat.completions.create(
                model=self.model,
                messages=_openai_messages(messages),  # type: ignore[arg-type]
                tools=_openai_tools(tools) or None,  # type: ignore[arg-type]
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            content_parts: List[str] = []
            tc_frags: Dict[int, Dict[str, Any]] = {}
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                if delta.content:
                    content_parts.append(delta.content)
                    if on_delta is not None:
                        on_delta(delta.content)
                for tc in delta.tool_calls or []:
                    idx = getattr(tc, "index", 0)
                    frag = tc_frags.setdefault(
                        idx, {"id": None, "name": "", "arguments": ""}
                    )
                    if getattr(tc, "id", None):
                        frag["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            frag["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            frag["arguments"] += fn.arguments
            tool_calls = None
            if tc_frags:
                tool_calls = [
                    _ToolCall(
                        name=frag["name"],
                        arguments=frag["arguments"],
                        call_id=frag["id"],
                    )
                    for _, frag in sorted(tc_frags.items())
                ]
            return _ToolResponse(content="".join(content_parts), tool_calls=tool_calls)
        except Exception as e:
            logger.error("OpenAI generate_with_tools_stream failed: %s", e)
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
        try:
            kwargs = _build_anthropic_request(
                self.model, self.max_tokens, messages, tools
            )
            response = self.client.messages.create(**kwargs)
            return _tool_response_from_anthropic(response)
        except Exception as e:
            logger.error("Anthropic generate_with_tools failed: %s", e)
            return _ToolResponse(content=f"AI error (Anthropic): {e}", tool_calls=None)

    def generate_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: list,
        on_delta: Optional[Callable[[str], None]] = None,
    ) -> Any:
        """Generate a tool-calling response via Anthropic, streaming text deltas.

        Each text chunk is passed to ``on_delta`` (called from the worker thread
        that runs this call) as it arrives. Returns the same normalized
        ``_ToolResponse`` as :meth:`generate_with_tools`.
        """
        try:
            kwargs = _build_anthropic_request(
                self.model, self.max_tokens, messages, tools
            )
            with self.client.messages.stream(**kwargs) as stream:
                if on_delta is not None:
                    for text in stream.text_stream:
                        if text:
                            on_delta(text)
            return _tool_response_from_anthropic(stream.get_final_message())
        except Exception as e:
            logger.error("Anthropic generate_with_tools_stream failed: %s", e)
            return _ToolResponse(content=f"AI error (Anthropic): {e}", tool_calls=None)


def _python_type_to_json(annotation: Any) -> Dict[str, Any]:
    """Map a Python annotation to a JSON Schema fragment."""
    import typing

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Optional / Union with None
    if origin is typing.Union and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            schema = _python_type_to_json(non_none[0])
            schema["nullable"] = True
            return schema
    if origin is typing.Optional if hasattr(typing, "Optional") else None:
        pass

    # List / Sequence
    if origin in (list, typing.List, typing.Sequence, typing.Iterable):
        item_type = args[0] if args else str
        return {"type": "array", "items": _python_type_to_json(item_type)}

    # Dict / Mapping
    if origin in (dict, typing.Dict, typing.Mapping):
        return {"type": "object"}

    # Primitive mapping
    if annotation is str or annotation is None or annotation is Any:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is list:
        return {"type": "array", "items": {"type": "string"}}
    if annotation is dict:
        return {"type": "object"}
    return {"type": "string"}


def _function_to_tool_schema(func: Any) -> Dict[str, Any]:
    """Convert a Python callable into an OpenAI/Anthropic tool schema."""
    import inspect

    _parse_docstring = None
    try:
        from docstring_parser import parse as _docstring_parse

        _parse_docstring = _docstring_parse
    except Exception:  # pragma: no cover
        _parse_docstring = None

    name = getattr(func, "__name__", str(func))
    doc = inspect.getdoc(func) or ""
    description = doc.strip().split("\n", 1)[0] if doc.strip() else name

    param_descriptions: Dict[str, str] = {}
    if _parse_docstring is not None:
        try:
            parsed = _parse_docstring(doc)
            for p in parsed.params:
                if p.arg_name:
                    param_descriptions[p.arg_name] = (p.description or "").strip()
        except Exception:
            param_descriptions = {}

    sig = inspect.signature(func)
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            annotation = str
        schema = _python_type_to_json(annotation)
        if pname in param_descriptions:
            schema["description"] = param_descriptions[pname]
        properties[pname] = schema
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    parameters: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


class _FunctionCall:
    """Mimics Ollama's function-call object for cloud providers."""

    def __init__(self, name: str, arguments: Any) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    """Mimics Ollama's ToolCall object for cloud providers."""

    def __init__(
        self, name: str, arguments: Any, call_id: Optional[str] = None
    ) -> None:
        self.id = call_id or str(uuid.uuid4())
        self.function = _FunctionCall(name, arguments)
        self.function.arguments = arguments


class _ToolResponse:
    """Lightweight wrapper to normalize tool-calling responses across providers."""

    def __init__(self, content: str, tool_calls: Optional[list] = None) -> None:
        """Initialize the tool response wrapper."""
        self.content = content
        self.tool_calls = tool_calls
        self.role = "assistant"
        self.message = self

    @property
    def tool_calls_list(self) -> Optional[list]:
        return self.tool_calls


def _anthropic_tool_schema(t: Any) -> Dict[str, Any]:
    """Convert one tool (dict or callable) to an Anthropic tool schema."""
    if isinstance(t, dict) and "function" in t:
        fn = t["function"]
    elif callable(t):
        schema = _function_to_tool_schema(t)
        fn = schema["function"]
    else:
        return cast(Dict[str, Any], t)  # already Anthropic-shaped
    return {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {}),
    }


def _build_anthropic_request(
    model: str,
    max_tokens: int,
    messages: List[Dict[str, Any]],
    tools: list,
) -> Dict[str, Any]:
    """Assemble an Anthropic messages kwargs dict from Ollama-style messages."""
    ant_tools = [_anthropic_tool_schema(t) for t in tools]
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "tools": ant_tools if ant_tools else None,
    }

    system_msg = None
    ant_messages: List[Dict[str, Any]] = []
    # Tool results are collected into a pending user message so they follow the
    # assistant turn that requested them (Anthropic requires alternating roles).
    pending_tool_results: list = []

    def flush_tool_results() -> None:
        nonlocal pending_tool_results
        if pending_tool_results:
            ant_messages.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results = []

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "system":
            system_msg = m.get("content", "")
            continue
        if role == "assistant":
            flush_tool_results()
            content_blocks = []
            text = m.get("content")
            if text:
                content_blocks.append({"type": "text", "text": text})
            for tc in m.get("tool_calls") or []:
                fn = getattr(tc, "function", None)
                if fn is None and isinstance(tc, dict):
                    fn = tc.get("function", {})
                name = (
                    getattr(fn, "name", None)
                    if not isinstance(fn, dict)
                    else fn.get("name")
                )
                args = (
                    getattr(fn, "arguments", None)
                    if not isinstance(fn, dict)
                    else fn.get("arguments")
                )
                cid = (
                    getattr(tc, "id", None)
                    if not isinstance(tc, dict)
                    else tc.get("id")
                )
                if isinstance(args, str):
                    try:
                        import json as _json

                        args = _json.loads(args)
                    except Exception:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": cid or str(uuid.uuid4()),
                        "name": name,
                        "input": args,
                    }
                )
            if not content_blocks:
                content_blocks = [{"type": "text", "text": ""}]
            ant_messages.append({"role": "assistant", "content": content_blocks})
        elif role == "tool":
            tool_call_id = m.get("tool_call_id")
            if not tool_call_id:
                tool_call_id = str(uuid.uuid4())
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": m.get("content", ""),
                }
            )
        else:
            flush_tool_results()
            content = m.get("content", "")
            ant_messages.append({"role": str(role or "user"), "content": content})

    flush_tool_results()

    if system_msg:
        kwargs["system"] = system_msg
    kwargs["messages"] = (
        ant_messages if ant_messages else [{"role": "user", "content": ""}]
    )
    return kwargs


def _tool_response_from_anthropic(response: Any) -> "_ToolResponse":
    """Convert an Anthropic message into a normalized ``_ToolResponse``."""
    tool_calls = None
    for block in response.content:
        if block.type == "tool_use":
            if tool_calls is None:
                tool_calls = []
            tool_calls.append(
                _ToolCall(name=block.name, arguments=block.input, call_id=block.id)
            )
    text_content = ""
    for block in response.content:
        if block.type == "text":
            text_content += block.text
    return _ToolResponse(content=text_content, tool_calls=tool_calls)


def _openai_tools(tools: list) -> List[Dict[str, Any]]:
    """Convert tools to OpenAI function-tool format."""
    oai_tools: List[Dict[str, Any]] = []
    for t in tools:
        if isinstance(t, dict) and "function" in t:
            oai_tools.append(t)
        elif callable(t):
            oai_tools.append(_function_to_tool_schema(t))
        else:
            oai_tools.append({"type": "function", "function": t})
    return oai_tools


def _openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize Ollama-style messages to OpenAI chat format."""
    norm_messages: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"):
            tc_list = []
            for tc in m["tool_calls"]:
                fn = getattr(tc, "function", None)
                if fn is None and isinstance(tc, dict):
                    fn = tc.get("function", {})
                name = (
                    getattr(fn, "name", None)
                    if not isinstance(fn, dict)
                    else fn.get("name")
                )
                args = (
                    getattr(fn, "arguments", None)
                    if not isinstance(fn, dict)
                    else fn.get("arguments")
                )
                cid = (
                    getattr(tc, "id", None)
                    if not isinstance(tc, dict)
                    else tc.get("id")
                )
                if isinstance(args, (dict, list)):
                    import json as _json

                    args = _json.dumps(args)
                tc_list.append(
                    {
                        "id": cid or str(uuid.uuid4()),
                        "type": "function",
                        "function": {"name": name, "arguments": args or "{}"},
                    }
                )
            norm_messages.append(
                {
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": tc_list,
                }
            )
        elif isinstance(m, dict) and m.get("role") == "tool":
            norm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id") or str(uuid.uuid4()),
                    "content": m.get("content", ""),
                }
            )
        else:
            norm_messages.append(m)
    return norm_messages


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
