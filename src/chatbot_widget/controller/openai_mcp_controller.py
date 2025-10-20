import json
import requests
from openai import OpenAI
from .openai_controller import OpenAIController


class OpenAIMCPController(OpenAIController):
    """OpenAI controller with MCP tool integration."""

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__(model=model)
        self.mcp_servers = {}  # name -> {"base_url": str, "tools": list}

    # ---------------------------------------------------------------
    # MCP server management
    # ---------------------------------------------------------------
    def register_mcp_server(self, name: str, base_url: str):
        """Register an MCP server and discover available tools."""
        try:
            resp = requests.get(f"{base_url}/tools")
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to reach MCP server {name}: {resp.status_code}")
            data = resp.json()
            tools = data.get("tools", [])
            self.mcp_servers[name] = {"base_url": base_url.rstrip("/"), "tools": tools}
            return f"🔗 Registered MCP server **{name}** with {len(tools)} tool(s)."
        except Exception as e:
            return f"⚠️ Error registering MCP server {name}: {e}"

    # ---------------------------------------------------------------
    # Command handler (extended)
    # ---------------------------------------------------------------
    def _execute_command(self, command: str):
        """Handle extended commands including MCP tools."""
        cmd = command.lower().strip()

        # --- existing commands ---
        if cmd in ("/clear", "/reset"):
            self.history.clear()
            return "🧹 Conversation history cleared."

        elif cmd in ("/help", "/?"):
            return (
                "**Available commands:**\n\n"
                "- `/help`: show this help\n"
                "- `/clear`: clear conversation\n"
                "- `/context`: show stored conversation\n"
                "- `/mcp`: list registered MCP servers\n"
                "- `/mcp <server>`: show tools for one server\n"
            )

        elif cmd == "/context":
            if not self.history:
                return "_(no context stored)_"
            formatted_blocks = []
            for m in self.history[-5:]:
                role = m["role"].capitalize()
                content = m["content"].strip()
                formatted_blocks.append(f"**{role}:**\n\n{content}")
            separator = '<hr style="border:none;border-top:1px solid #a8c7ff;margin:6px 0;">'
            return f"🧠 **Current context (last 5):**\n\n{separator.join(formatted_blocks)}"

        # --- new MCP commands ---
        elif cmd.startswith("/mcp"):
            parts = cmd.split()
            if len(parts) == 1:
                if not self.mcp_servers:
                    return "⚠️ No MCP servers registered."
                msg = ["🧩 **Registered MCP servers:**"]
                for name, info in self.mcp_servers.items():
                    msg.append(f"- **{name}** → {info['base_url']} ({len(info['tools'])} tools)")
                return "\n".join(msg)
            else:
                name = parts[1]
                server = self.mcp_servers.get(name)
                if not server:
                    return f"⚠️ No MCP server named '{name}'."
                msg = [f"🧩 **Tools for {name}:**"]
                for t in server["tools"]:
                    desc = t.get("description", "")
                    params = ", ".join(t.get("input_schema", {}).get("properties", {}).keys())
                    msg.append(f"- `{t['name']}({params})` — {desc}")
                return "\n".join(msg)

        else:
            return f"❓ Unknown command: `{command}`"

    # ---------------------------------------------------------------
    # Main entrypoint (override)
    # ---------------------------------------------------------------
    def handle_input(self, msg: str):
        """Handle normal chat + tool-calling."""
        if not msg.strip():
            return

        if msg.startswith("/"):
            reply = self._execute_command(msg.strip())
            if self._on_response:
                self._on_response(reply)
            return

        # normal message flow
        self.history.append({"role": "user", "content": msg})
        tools = self._get_all_tools()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=tools if tools else None,
            )

            message = response.choices[0].message

            # handle tool calls if any
            if hasattr(message, "tool_calls") and message.tool_calls:
                for call in message.tool_calls:
                    tool_name = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    result = self._call_mcp_tool(tool_name, args)
                    self.history.append({"role": "assistant", "content": f"🧩 Tool result:\n\n{result}"})
                    if self._on_response:
                        self._on_response(f"🧩 **Tool `{tool_name}` result:**\n\n{result}")
            else:
                reply = message.content
                self.history.append({"role": "assistant", "content": reply})
                if self._on_response:
                    self._on_response(reply)

        except Exception as e:
            if self._on_response:
                self._on_response(f"⚠️ Error: {e}")

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    def _get_all_tools(self):
        """Return all MCP tools in OpenAI-compatible format."""
        tools = []
        for srv in self.mcp_servers.values():
            for t in srv["tools"]:
                func = {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                tools.append(func)
        return tools

    def _call_mcp_tool(self, tool_name: str, args: dict):
        """Find and call a matching MCP tool by name."""
        for name, srv in self.mcp_servers.items():
            for t in srv["tools"]:
                if t["name"] == tool_name:
                    url = f"{srv['base_url']}/tools/{tool_name}"
                    try:
                        resp = requests.post(url, json=args)
                        if resp.status_code != 200:
                            return f"Error {resp.status_code}: {resp.text}"
                        return json.dumps(resp.json(), indent=2)
                    except Exception as e:
                        return f"⚠️ Error calling {tool_name} on {name}: {e}"
        return f"⚠️ Tool '{tool_name}' not found in any registered MCP server."
