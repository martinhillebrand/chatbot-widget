import json
from openai import OpenAI
from .openai_controller import OpenAIController


class OpenAIMCPController(OpenAIController):
    """OpenAI controller with integrated MCPServerManager support."""

    def __init__(self, mcp_manager, model: str = "gpt-4.1"):
        super().__init__(model=model)
        self.mcp_manager = mcp_manager  # existing MCPServerManager instance

    # ---------------------------------------------------------------
    # Command handler
    # ---------------------------------------------------------------
    def _execute_command(self, command: str):
        """Handle commands including MCP interactions."""
        cmd = command.strip()

        if cmd in ("/clear", "/reset"):
            self.history.clear()
            return "Conversation history cleared."

        elif cmd in ("/help", "/?"):
            return (
                "Available commands:\n"
                "- /help           Show this help\n"
                "- /clear          Clear conversation\n"
                "- /context        Show stored conversation\n"
                "- /mcp            List MCP servers\n"
                "- /mcp <server>   List tools for a server\n"
            )

        elif cmd == "/context":
            if not self.history:
                return "(no context stored)"
            blocks = []
            for m in self.history[-5:]:
                role = m["role"].capitalize()
                blocks.append(f"{role}:\n{m['content']}\n")
            return "Current context (last 5):\n\n" + "\n".join(blocks)

        elif cmd.startswith("/mcp"):
            parts = cmd.split()
            servers = self.mcp_manager._servers

            if len(parts) == 1:
                if not servers:
                    return "No MCP servers are currently registered."
                msg = ["Registered MCP servers:"]
                for name, info in servers.items():
                    msg.append(f"- {name}: port={info.get('port')}")
                return "\n".join(msg)

            # /mcp <server>
            elif len(parts) == 2:
                name = parts[1]
                if name not in servers:
                    return f"No MCP server named '{name}'."
                try:
                    tools = self.mcp_manager.list_tools(name)
                    return f"Tools for server '{name}':\n" + str(tools)
                except Exception as e:
                    return f"Error listing tools for '{name}': {e}"

            else:
                return "Invalid MCP command. Use '/mcp' or '/mcp <server>'."

        else:
            return f"Unknown command: {command}"

    # ---------------------------------------------------------------
    # Chat + tool handling
    # ---------------------------------------------------------------
    def handle_input(self, msg: str):
        """Handle new user input and possible tool calls."""
        if not msg.strip():
            return

        if msg.startswith("/"):
            reply = self._execute_command(msg)
            if self._on_response:
                self._on_response(reply)
            return

        # Add user message
        self.history.append({"role": "user", "content": msg})

        try:
            tools = self._get_all_tools()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=tools if tools else None,
            )
            message = response.choices[0].message

            # --- Tool call ---
            if hasattr(message, "tool_calls") and message.tool_calls:
                for call in message.tool_calls:
                    tool_name = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    result = self._call_mcp_tool(tool_name, args)
                    self.history.append(
                        {"role": "assistant", "content": f"Tool result:\n{result}"}
                    )
                    if self._on_response:
                        self._on_response(f"Tool result:\n{result}")
            else:
                reply = message.content
                self.history.append({"role": "assistant", "content": reply})
                if self._on_response:
                    self._on_response(reply)

        except Exception as e:
            if self._on_response:
                self._on_response(f"Error: {e}")

    # ---------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------
    def _get_all_tools(self):
        """Collect all tools from MCPServerManager."""
        tools = []
        for name in self.mcp_manager._servers.keys():
            try:
                tool_objs = self.mcp_manager.list_tools(name)
                for t in tool_objs.tools:  # FastMCP returns a model with .tools
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": getattr(t, "description", ""),
                                "parameters": getattr(t, "inputSchema", {}),
                            },
                        }
                    )
            except Exception:
                continue
        return tools

    def _call_mcp_tool(self, tool_name: str, args: dict):
        """Find and execute tool via MCPServerManager.test_tool."""
        for name in self.mcp_manager._servers.keys():
            try:
                tools = self.mcp_manager.list_tools(name)
                for t in tools.tools:
                    if t.name == tool_name:
                        result = self.mcp_manager.test_tool(name, tool_name, args)
                        return str(result)
            except Exception:
                continue
        return f"Tool '{tool_name}' not found in any MCP server."
