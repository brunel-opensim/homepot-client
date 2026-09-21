"""Agentic AI — ReAct Agent Loop.

Implements a multi-step reasoning loop where the LLM can autonomously
query additional data sources via tool calls, building up evidence before
producing a final answer.

See docs/ai-agentic.md for the full architecture.
"""

from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional

from ai.llm import LLMService
from ai.tools import TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 5
TOTAL_TIMEOUT_SECONDS = 60
TOOL_RESULT_MAX_CHARS = 1500

AGENT_SYSTEM_PROMPT = """\
You are the HOMEPOT System Diagnostics AI with agentic tool-calling capabilities.

You have access to tools that let you investigate device issues step by step.
When you receive a question, think about what data you need, call the appropriate
tool, observe the result, and continue reasoning until you have enough evidence
to provide a confident answer.

GUIDELINES:
- Call tools when you need specific data that isn't in the initial context.
- You can call multiple tools in sequence to build up a complete picture.
- When you have enough evidence, provide a clear, actionable final answer.
- If a tool returns an error or no data, acknowledge it and try a different approach.
- Always ground your answer in the data you retrieve — never speculate.
- Keep your final answer concise and focused on the technician's question.
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolCallRecord:
    """Record of a single tool call made during the agent loop."""

    tool_name: str
    iteration: int
    arguments: Dict[str, Any]
    result_preview: str = ""


@dataclass
class AgentResult:
    """Result of an agentic investigation."""

    response: str
    iterations: int
    tools_called: List[ToolCallRecord]
    total_duration_ms: int
    fell_back_to_direct: bool = False


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


async def _execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a single tool by name with the given arguments.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Keyword arguments for the tool function.

    Returns:
        String result from the tool, or an error message.
    """
    entry = TOOL_REGISTRY.get(tool_name)
    if not entry:
        return f"Unknown tool: '{tool_name}'. Available tools: {list(TOOL_REGISTRY.keys())}"

    func, is_async = entry

    try:
        if is_async:
            result = await func(**arguments)  # type: ignore[operator]
        else:
            result = func(**arguments)  # type: ignore[operator]
    except TypeError as e:
        # Wrong arguments — tool signature mismatch
        return f"Invalid arguments for {tool_name}: {e}"
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return f"Tool {tool_name} failed: {e}"

    result_str = str(result)
    if len(result_str) > TOOL_RESULT_MAX_CHARS:
        result_str = result_str[:TOOL_RESULT_MAX_CHARS] + "... (truncated)"
    return result_str


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def run_agent(
    query: str,
    context: str,
    llm: LLMService,
    device_id: Optional[str] = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentResult:
    """Run the ReAct agent loop.

    The agent receives the query and pre-assembled context, then iteratively
    calls tools to investigate before producing a final answer.

    Args:
        query: The user's question.
        context: Pre-assembled context from ContextBuilder.
        llm: LLM service instance.
        device_id: Optional device ID for context.
        max_iterations: Maximum number of tool-calling iterations.

    Returns:
        AgentResult with the final response and metadata.
    """
    start_time = time.monotonic()
    tools_called: List[ToolCallRecord] = []

    # Build initial messages
    system_content = AGENT_SYSTEM_PROMPT
    if device_id:
        system_content += f"\nCurrent device under investigation: {device_id}"

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]

    last_response_text = ""

    for iteration in range(max_iterations):
        # Check total timeout
        elapsed = time.monotonic() - start_time
        if elapsed > TOTAL_TIMEOUT_SECONDS:
            logger.warning(
                "Agent loop timeout after %.1fs at iteration %d",
                elapsed,
                iteration,
            )
            break

        # Call LLM with tools
        try:
            response = llm.generate_with_tools(
                messages=messages,
                tools=TOOL_FUNCTIONS,
            )
        except Exception as e:
            logger.error("LLM call failed at iteration %d: %s", iteration, e)
            break

        # Append assistant message to history
        assistant_msg: Dict[str, Any] = {
            "role": response.message.role,
            "content": response.message.content or "",
        }
        if response.message.tool_calls:
            assistant_msg["tool_calls"] = response.message.tool_calls
        messages.append(assistant_msg)

        # Check if model produced a final answer (no tool calls)
        if not response.message.tool_calls:
            last_response_text = response.message.content or ""
            break

        # Execute each tool call
        for call in response.message.tool_calls:
            tool_name = call.function.name
            arguments = dict(call.function.arguments)

            # Record the call
            record = ToolCallRecord(
                tool_name=tool_name,
                iteration=iteration + 1,
                arguments=arguments,
            )
            tools_called.append(record)

            # Execute tool
            result = await _execute_tool(tool_name, arguments)

            # Update record with result preview
            record.result_preview = result[:200]

            logger.info(
                "Agent tool call: %s(%s) -> %d chars",
                tool_name,
                arguments,
                len(result),
            )

            # Feed result back as tool message
            messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": result,
                }
            )

    # If we exhausted iterations without a final answer, ask for one
    if not last_response_text:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Please provide your final answer based on all the information "
                    "you have gathered so far. Do not call any more tools."
                ),
            }
        )
        try:
            response = llm.generate_with_tools(
                messages=messages,
                tools=TOOL_FUNCTIONS,
            )
            last_response_text = response.message.content or (
                "I was unable to complete the investigation within the allowed "
                "iterations. Please try a more specific question."
            )
        except Exception as e:
            logger.error("Final answer LLM call failed: %s", e)
            last_response_text = (
                "I was unable to complete the investigation. "
                "Please try a more specific question."
            )

    total_ms = int((time.monotonic() - start_time) * 1000)

    return AgentResult(
        response=last_response_text,
        iterations=len(tools_called),
        tools_called=tools_called,
        total_duration_ms=total_ms,
    )
