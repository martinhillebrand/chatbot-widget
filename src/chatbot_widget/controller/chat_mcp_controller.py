import json
import uuid
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver

from chatbot_widget.mcp.server_manager import MCPServerManager
from chatbot_widget.ui.chat_view import ChatView
from chatbot_widget.utils.utils import run_async


@dataclass
class _ToolEvent:
    call_id: str | None
    name: str
    payload: str
    run_key: str | None


class ChatMCPController:
    """Bridge between MCP-managed tools, an LLM agent, and the notebook UI."""

    def __init__(self, mcp_server_manager: MCPServerManager, model: Any = "openai:gpt-5"):
        self.mcp = mcp_server_manager
        self.model_spec = model
        self._busy = False
        self._seen_msgs = 0
        self._streaming_enabled = True
        self.system_prompt = (
            "You are an assistant whose replies render inside a Markdown-based chat UI.\n"
            "- Keep responses concise and structured.\n"
            "- Use Markdown lists (with '-') for enumerations.\n"
            "- Wrap multi-line code in fenced code blocks (```lang).\n"
            "- Avoid raw HTML unless explicitly requested."
        )
        self._tool_run_lookup: dict[str, str] = {}
        self._pending_calls: dict[str, list[str]] = {}
        self._tool_metadata: dict[str, str] = {}

        self.lookup_tool_server: dict[str, str] = {}
        self.server_port_dict: dict[str, int] = {}

        self.client = MultiServerMCPClient({})
        self.agent = None

        self.ui = ChatView()
        self.ui.on_send(self.handle_input)

        self._refresh_client(force=True)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def display(self):
        self.ui.display()

    def set_model(self, model: Any):
        """Switch to a different chat model provider (e.g. ``'anthropic:claude-3'``)."""
        self.model_spec = model
        self._streaming_enabled = True
        self._initialize_agent()

    def set_system_prompt(self, prompt: str):
        """Override the default system instructions for LLM responses."""
        self.system_prompt = prompt

    def _refresh_client(self, force: bool = False):
        latest_ports = self.mcp.get_server_port_dict()
        if not force and latest_ports == self.server_port_dict:
            self.lookup_tool_server = self.mcp.get_tool_server_dict()
            return

        self.server_port_dict = latest_ports
        self.lookup_tool_server = self.mcp.get_tool_server_dict()

        client_dict = {
            server: {"transport": "streamable_http", "url": f"http://localhost:{port}/mcp"}
            for server, port in self.server_port_dict.items()
        }
        self.client = MultiServerMCPClient(client_dict)
        self._initialize_agent()

    def _initialize_agent(self):
        model_instance = self._load_model(self.model_spec, streaming=self._streaming_enabled)
        tools = run_async(self.client.get_tools()) if hasattr(self.client, "get_tools") else []
        self.agent = create_agent(model_instance, tools, checkpointer=InMemorySaver())
        self._seen_msgs = 0

    @staticmethod
    def _parse_model_spec(model: str) -> tuple[str, str]:
        if ":" in model:
            provider, model_name = model.split(":", 1)
        else:
            provider, model_name = "openai", model
        return provider.lower(), model_name

    def _load_model(self, model: Any, *, streaming: bool):
        """Instantiate a LangChain chat model from a shorthand string or custom instance."""
        if hasattr(model, "invoke"):
            return model
        if isinstance(model, str):
            provider, name = self._parse_model_spec(model)
            if provider in ("openai", "azure-openai"):
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(model=name, temperature=0, streaming=streaming)
            if provider == "anthropic":
                try:
                    from langchain_anthropic import ChatAnthropic
                except ImportError as exc:  # pragma: no cover - optional dependency
                    raise RuntimeError(
                        "langchain-anthropic is required for anthropic models. Install it first."
                    ) from exc
                return ChatAnthropic(model=name, streaming=streaming)
            if provider == "ollama":
                from langchain_community.chat_models import ChatOllama

                return ChatOllama(model=name, streaming=streaming)
            raise ValueError(f"Unknown model provider '{provider}'.")
        raise TypeError("Model must be a string shorthand or a LangChain chat model instance.")

    # ------------------------------------------------------------------
    # Main entrypoint
    # ------------------------------------------------------------------
    def handle_input(self, msg: str):
        if not msg.strip():
            return

        if msg.startswith("/"):
            reply = self._execute_command(msg.strip())
            self.ui.receive_message(reply)
            return

        if self._busy:
            self.ui.receive_message("⚠️ Another request is still running. Please wait for it to finish.", "bot")
            return

        self._busy = True

        try:
            self._refresh_client()
            if self.agent is None:
                raise RuntimeError("Agent not initialised. Ensure at least one MCP server is registered.")
        except Exception as exc:
            self._busy = False
            self.ui.set_busy(False)
            self.ui.receive_message(f"⚠️ Setup error: {exc}", "bot")
            return

        self.ui.set_busy(True)
        self.ui.show_waiting_indicator()
        stream_id = self.ui.start_stream("bot")

        try:
            messages = self._build_messages(msg)
            run_async(self._run_conversation(messages, stream_id))
        except Exception as exc:  # pragma: no cover - defensive (run_async should swallow)
            self._handle_error(exc, stream_id)

    async def _run_conversation(self, messages: list[dict[str, str]], stream_id: str):
        inputs = {"messages": messages}
        config = {"configurable": {"thread_id": "1"}}

        partial_text = ""
        try:
            async for event in self._astream_events(inputs, config):
                kind = event.get("event")
                data = event.get("data", {})

                if kind == "on_tool_start":
                    tool_event = self._format_tool_event(event, kind)
                    if tool_event:
                        call_id = self._register_tool_start(
                            tool_event.name, tool_event.call_id, tool_event.run_key
                        )
                        self.ui.receive_tool_call(call_id, tool_event.name, tool_event.payload)
                elif kind == "on_tool_end":
                    tool_event = self._format_tool_event(event, kind)
                    if tool_event:
                        call_id = self._register_tool_end(
                            tool_event.name, tool_event.call_id, tool_event.run_key
                        )
                        resolved_name = self._tool_metadata.get(call_id, tool_event.name)
                        self.ui.receive_tool_reply(call_id, resolved_name, tool_event.payload)
                elif kind == "on_chat_model_stream":
                    delta = self._extract_text(data.get("chunk"))
                    if delta:
                        partial_text += delta
                        self.ui.stream_update(stream_id, partial_text)
                elif kind == "on_chat_model_end":
                    completion = self._extract_text(data.get("output"))
                    if completion and completion not in partial_text:
                        partial_text += completion
                        self.ui.stream_update(stream_id, partial_text)
        except Exception as exc:
            # Fallback to a single-shot invoke if streaming is unsupported.
            error_text = str(exc)
            unsupported_stream = any(
                token in error_text.lower()
                for token in (
                    "must be verified to stream",
                    "unsupported_value",
                    "streaming is not enabled",
                )
            )
            if unsupported_stream and self._streaming_enabled:
                self._streaming_enabled = False
                self._initialize_agent()
                await self._fallback_invoke(inputs, config, stream_id)
            elif isinstance(exc, AttributeError) or "astream" in error_text:
                await self._fallback_invoke(inputs, config, stream_id)
            else:
                self._handle_error(exc, stream_id)
        else:
            if partial_text.strip():
                self.ui.end_stream(stream_id, partial_text)
            else:
                # If nothing was streamed, fetch the final response from invoke
                await self._fallback_invoke(inputs, config, stream_id)
        finally:
            self._busy = False
            self.ui.set_busy(False)
            self._tool_run_lookup.clear()
            self._pending_calls.clear()
            # keep metadata for UI to reference existing entries

    async def _astream_events(self, inputs: dict[str, Any], config: dict[str, Any]):
        if hasattr(self.agent, "astream_events"):
            async for event in self.agent.astream_events(inputs, config, version="v1"):
                yield event
        else:
            raise AttributeError("Agent does not expose streaming events.")

    async def _fallback_invoke(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        stream_id: str,
    ):
        result = await self.agent.ainvoke(inputs, config)

        messages = result.get("messages", []) if isinstance(result, dict) else []
        new_msgs = messages[self._seen_msgs :]
        self._seen_msgs = len(messages)

        formatted = []
        for message in new_msgs:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for call in message.tool_calls:
                    tool_name = call.get("name", "tool")
                    server_name = self.lookup_tool_server.get(tool_name, "unknown")
                    full_name = f"{server_name}::{tool_name}"
                    args_obj = call.get("args", {})
                    try:
                        payload = json.dumps(args_obj, indent=2, ensure_ascii=False)
                    except TypeError:
                        payload = str(args_obj)
                    call_id = call.get("id") or str(uuid.uuid4())
                    call_id = self._register_tool_start(full_name, call_id, None)
                    self.ui.receive_tool_call(call_id, full_name, payload)
            elif getattr(message, "name", None) and message.__class__.__name__ == "ToolMessage":
                content_obj = message.content
                if isinstance(content_obj, (dict, list)):
                    try:
                        payload = json.dumps(content_obj, indent=2, ensure_ascii=False)
                    except TypeError:
                        payload = str(content_obj)
                else:
                    payload = str(content_obj)
                tool_name = getattr(message, "name", None)
                if tool_name and "::" in tool_name:
                    full_name = tool_name
                else:
                    server = self.lookup_tool_server.get(tool_name or "", "unknown")
                    base = tool_name or "tool"
                    full_name = f"{server}::{base}"
                call_id = getattr(message, "tool_call_id", None) or str(uuid.uuid4())
                call_id = self._register_tool_end(full_name, call_id, None)
                resolved_name = self._tool_metadata.get(call_id, tool_name or full_name)
                self.ui.receive_tool_reply(call_id, resolved_name, payload)
            elif message.__class__.__name__ == "AIMessage" and message.content:
                formatted.append(message.content if isinstance(message.content, str) else str(message.content))

        final_text = "\n\n".join(formatted).strip() or "⚠️ No response generated."
        self.ui.end_stream(stream_id, final_text)

    def _build_messages(self, user_input: str) -> list[dict[str, str]]:
        """Construct a LangChain-compatible message list with the active system prompt."""
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_input})
        return messages

    def _handle_error(self, exc: Exception, stream_id: str):
        self.ui.end_stream(stream_id, f"⚠️ Error: {exc}")
        self.ui.receive_message(f"⚠️ Error: {exc}", "bot")

    # ------------------------------------------------------------------
    # Stream parsing helpers
    # ------------------------------------------------------------------
    def _extract_text(self, chunk: Any) -> str:
        if chunk is None:
            return ""
        if isinstance(chunk, str):
            return chunk
        if hasattr(chunk, "content"):
            pieces = []
            for part in getattr(chunk, "content", []):
                if isinstance(part, str):
                    pieces.append(part)
                elif hasattr(part, "text"):
                    pieces.append(part.text)
                elif isinstance(part, dict) and "text" in part:
                    pieces.append(part["text"])
            return "".join(pieces)
        if hasattr(chunk, "text"):
            return chunk.text
        if isinstance(chunk, dict):
            return str(chunk.get("text") or chunk.get("content") or "")
        return ""

    def _format_tool_event(self, event: dict[str, Any], event_type: str) -> _ToolEvent | None:
        name = event.get("name") or event.get("data", {}).get("name")
        if not name:
            return None
        server = self.lookup_tool_server.get(name, "unknown")
        full_name = f"{server}::{name}"
        data = event.get("data", {}) or {}
        run_key = self._derive_run_key(event)
        call_id = data.get("id") or data.get("tool_call_id") or data.get("run_id")
        payload = data.get("input") or data.get("output") or {}
        if not isinstance(payload, str):
            try:
                payload = json.dumps(payload, indent=2, ensure_ascii=False)
            except TypeError:
                payload = str(payload)
        if event_type == "on_tool_end" and not call_id:
            call_id = self._pop_pending_call(full_name)
        return _ToolEvent(call_id, full_name, payload, run_key)

    def _derive_run_key(self, event: dict[str, Any]) -> str | None:
        data = event.get("data", {}) or {}
        for key in ("id", "run_id", "tool_call_id"):
            value = data.get(key)
            if value:
                return f"{key}:{value}"
        metadata = data.get("metadata") or {}
        if isinstance(metadata, dict):
            for key in ("run_id", "tool_call_id"):
                value = metadata.get(key)
                if value:
                    return f"meta_{key}:{value}"
        return None

    def _register_tool_start(self, tool_name: str, call_id: str | None, run_key: str | None) -> str:
        call_id = call_id or str(uuid.uuid4())
        if run_key:
            self._tool_run_lookup[run_key] = call_id
        queue = self._pending_calls.setdefault(tool_name, [])
        queue.append(call_id)
        self._tool_metadata[call_id] = tool_name
        return call_id

    def _register_tool_end(self, tool_name: str, call_id: str | None, run_key: str | None) -> str:
        if run_key and run_key in self._tool_run_lookup:
            call_id = self._tool_run_lookup.pop(run_key)
        queue = self._pending_calls.setdefault(tool_name, [])
        if call_id and call_id in queue:
            queue.remove(call_id)
        elif call_id is None and queue:
            call_id = queue.pop(0)
        else:
            call_id = call_id or str(uuid.uuid4())
        self._tool_metadata.setdefault(call_id, tool_name)
        return call_id

    def _pop_pending_call(self, tool_name: str) -> str | None:
        queue = self._pending_calls.get(tool_name)
        if queue:
            return queue.pop(0)
        return None

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------
    def _execute_command(self, msg: str):
        parts = msg.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            return self.__command_help()
        if cmd == "/context":
            return self.__command_context()
        if cmd == "/clear":
            return self.__command_clear()
        if cmd == "/servers":
            return self.__command_servers()
        if cmd == "/logs":
            return self.__command_logs(*args)
        if cmd == "/tools":
            return self.__command_tools()
        if cmd == "/testtool":
            return self.__command_testtool(*args)
        if cmd == "/checkall":
            return self.__command_checkall()
        return f"⚠️ Unknown command: {cmd}. Type /help for a list of commands."

    def __command_help(self):
        cmds = {
            "/help": "Show this help message",
            "/context": "Show current conversation context",
            "/clear": "Clear conversation history",
            "/servers": "List running MCP servers",
            "/logs <server> [n]": "Show the last n log lines for a server",
            "/tools": "List available MCP tools",
            "/testtool <server> <tool> [args_json]": "Invoke an MCP tool manually",
            "/checkall": "Check health of every tracked server",
        }
        return "\n".join([f"- **{k}** {v}" for k, v in cmds.items()])

    def __command_context(self):
        return "🧠 Context inspection not yet implemented."

    def __command_clear(self):
        if self.agent:
            self.agent.checkpointer = InMemorySaver()
        self._seen_msgs = 0
        return "🧹 Conversation history cleared."

    def __command_servers(self):
        servers = self.mcp.get_server_port_dict()
        if not servers:
            return "No active MCP servers."
        return "\n".join([f"- {name}: port {port}" for name, port in servers.items()])

    def __command_logs(self, server_name: str | None = None, n: str = "50"):
        if not server_name:
            return "Usage: /logs <server_name> [n]"
        try:
            line_count = int(n)
        except ValueError:
            line_count = 50
        result = self.mcp.show_logs(server_name, line_count)
        if not result or result.get("status") != "ok":
            return result.get("message", f"No logs found for {server_name}.")
        lines = "".join(result.get("lines", []))
        return (
            f"📜 **Logs for {server_name}** *(last {line_count} lines of {result.get('log_file')})*\n\n"
            f"```\n{lines.strip()}\n```"
        )

    def __command_tools(self):
        tools = self.mcp.get_tool_server_dict()
        if not tools:
            return "No tools available."
        return "\n".join([f"- {server} :: {tool}" for tool, server in sorted(tools.items())])

    def __command_testtool(self, server_name=None, tool_name=None, args_json="{}"):
        if not (server_name and tool_name):
            return "Usage: /testtool <server_name> <tool_name> [args_json]"
        try:
            args = json.loads(args_json)
        except Exception:
            return "⚠️ Invalid JSON for args."
        result = self.mcp.test_tool(server_name, tool_name, args)
        if not result:
            return "⚠️ Tool invocation returned no data."
        return json.dumps(result, indent=2, ensure_ascii=False)

    def __command_checkall(self):
        results = self.mcp.check_all()
        if isinstance(results, dict):
            lines = [f"- {name}: {'✅' if healthy else '⚠️'}" for name, healthy in results.items()]
            return "\n".join(lines)
        return str(results)
