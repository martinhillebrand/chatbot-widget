import subprocess, sys, os
import socket
import random
import time
import requests
from fastmcp.client import Client
import asyncio
import json

class MCPServerManager:
    """Utility to start/stop FastMCP servers from notebooks."""

    def __init__(self):
        self._servers = {}
    
    
    def _find_free_port(self, start: int = 8600, end: int = 8900):
        """Find an available TCP port in the MCP typical range."""
        for _ in range(50):
            port = random.randint(start, end)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("⚠️ Could not find a free port in range 8600–8900.")

    def start(self, name: str, script_path: str, port: int | None = None, log_file: str = None, **kwargs):
        """Start MCP server silently in background, forwarding arbitrary CLI args.

        Example:
            mcp.start(
                "random",
                "src/chatbot_widget/mcp/random_server.py",
                db_user="admin",
                db_pass="secret",
                debug=True
            )
        """
        if name in self._servers:
            print(f"⚠️ Server '{name}' already running.")
            return

        script_path = os.path.abspath(script_path)
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            return

        port = port or self._find_free_port()
        log_file = log_file or f"{name}_server.log"
        f = open(log_file, "w", encoding="utf-8")


        # Convert kwargs to CLI args like: --db_user admin --db_pass secret
        extra_args = []
        for k, v in kwargs.items():
            extra_args.append(f"--{k}")
            if v is not None and v is not True:
                extra_args.append(str(v))
            elif v is True:
                # flags (no value)
                continue

        proc = subprocess.Popen(
            [sys.executable, script_path, str(port)] + extra_args,
            stdout=f,
            stderr=f,
            cwd=os.path.dirname(script_path),
        )

        self._servers[name] = {
            "proc": proc,
            "file": f,
            "log_file": log_file,
            "port": port,
            "args": kwargs,
        }

        print(f"✅ Started '{name}' on port {port} (PID={proc.pid}) → logs: {log_file}")
        time.sleep(2)
        if not self.check_health(name, port):
            print(f"⚠️ Warning: '{name}' may not have started correctly. Check {log_file}.")


    def stop(self, name: str):
        """Stop a named MCP server (only if it's actually running)."""
        if name not in self._servers:
            print(f"⚠️ No server named '{name}' found in registry.")
            return

        info = self._servers[name]
        proc = info["proc"]
        port = info.get("port")

        # --- check if process is already dead ---
        if proc.poll() is not None:
            print(f"⚠️ Process for '{name}' already stopped (PID={proc.pid}).")
            self._servers.pop(name)
            return

        # --- optional: check HTTP health before killing ---
        healthy = self.check_health(name, port)
        if not healthy:
            print(f"⚠️ '{name}' not responding on port {port} — terminating anyway.")

        try:
            proc.terminate()
            proc.wait(timeout=3)
            info["file"].close()
            self._servers.pop(name)
            print(f"🛑 Stopped server '{name}' (port = {port}, PID={proc.pid}).")
        except Exception as e:
            print(f"❌ Error stopping '{name}': {e}")
    
    def restart(self, name: str, new_port: int | None = None):
        """Restart a running MCP server safely (same or new port)."""
        if name not in self._servers:
            print(f"⚠️ No running server named '{name}'. Use start() instead.")
            return

        info = self._servers[name]
        script_path = info.get("script_path")
        current_port = info.get("port")

        if not script_path or not os.path.exists(script_path):
            print(f"❌ Cannot restart '{name}': original script path missing or invalid.")
            return

        # --- stop the server first ---
        print(f"🔄 Restarting '{name}'...")
        self.stop(name)

        # --- confirm process is dead ---
        proc = info["proc"]
        try:
            proc.wait(timeout=2)
        except Exception:
            print(f"⚠️ Old process for '{name}' did not terminate cleanly. Forcing kill.")
            proc.kill()

        # --- restart on same or new port ---
        port = new_port or current_port
        self.start(name, script_path, port=port)



    def stop_all(self):
        """Stop all running MCP servers."""
        if not self._servers:
            print("ℹ️ No MCP servers are currently running — nothing to stop.")
            return

        for name in list(self._servers.keys()):
            self.stop(name)


    def show_logs(self, name: str, n: int = 80, remove_windows_warnings: bool = True):
        """Display the last n log lines of a running server."""
        if name not in self._servers:
            log_file = f"{name}_server.log"
            if not os.path.exists(log_file):
                print(f"⚠️ No logs found for '{name}'.")
                return
        else:
            log_file = self._servers[name]["log_file"]

        try:
            with open(log_file, "r") as f:
                lines = f.readlines()[-n:]
            if remove_windows_warnings:
                lines = self._filter_logs(lines)
            print(f"\n📜 Last {n} lines from {log_file}:\n" + "".join(lines))
        except Exception as e:
            print(f"⚠️ Could not read logs: {e}")


    def _filter_logs(self, lines: list[str]) -> list[str]:
        """
        Remove Windows asyncio noise blocks (WinError 10054 / Proactor transport).
        Drops from the first noisy line until the next log prefix (INFO/WARNING/ERROR/DEBUG).
        """
        LOG_PREFIXES = ("INFO:", "WARNING:", "ERROR:", "DEBUG:")
        NOISE_TRIGGERS = (
            "[WinError 10054]",
            "ConnectionResetError",
            "Exception in callback _ProactorBasePipeTransport._call_connection_lost",
            "_ProactorBasePipeTransport._call_connection_lost",
        )

        filtered = []
        skipping = False

        for line in lines:
            if not skipping:
                if any(t in line for t in NOISE_TRIGGERS):
                    skipping = True
                    continue
                filtered.append(line)
            else:
                # stop skipping when a new log record starts
                if line.lstrip().startswith(LOG_PREFIXES):
                    skipping = False
                    filtered.append(line)
                # else keep skipping traceback lines

        # optional: collapse extra blank lines
        compact = []
        prev_blank = False
        for ln in filtered:
            is_blank = not ln.strip()
            if is_blank and prev_blank:
                continue
            compact.append(ln)
            prev_blank = is_blank
        return compact


    def check_health(self, name: str, port: int | None = None):
        """Check if an MCP server is reachable and responding via /mcp."""
        if name not in self._servers and port is None:
            print(f"⚠️ Unknown server '{name}' (and no port provided).")
            return False

        if name in self._servers:
            port = self._servers[name].get("port", port)

        base_url = f"http://127.0.0.1:{port}"

        # check: use FastMCP client to ping
        try:
            import asyncio
            from fastmcp.client import Client

            async def _check():
                async with Client(f"{base_url}/mcp") as c:
                    await c.ping()
                    print(f"✅ '{name}' healthy → Server is reachable")
                    await c.close()  # ✅ explicitly close client session
                    return True

            # Run safely in CLI or Jupyter
            try:
                return asyncio.run(_check())
            except RuntimeError:
                import nest_asyncio
                nest_asyncio.apply()
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(_check())
                return result

        except Exception as e:
            print(f"⚠️ '{name}' MCP Ping failed: {e}")
            return False



    def check_all(self):
        """Check health of all running servers."""
        for name, info in self._servers.items():
            port = info.get("port")
            self.check_health(name, port)


    def list_tools(self, name: str, port: int | None = None):
        """List all available tools for a given MCP server (with full metadata)."""
        if name not in self._servers and port is None:
            print(f"⚠️ Unknown server '{name}' (and no port provided).")
            return []

        if name in self._servers:
            port = self._servers[name].get("port", port)

        base_url = f"http://127.0.0.1:{port}/mcp"

        async def _list():
            async with Client(base_url) as c:
                tools = await c.list_tools()
                await c.close()
                return tools

        try:
            return asyncio.run(_list())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_list())

    def test_tool(self, server_name: str, tool_name: str, args: dict | None = None):
        """Directly call an MCP tool and return raw result for debugging."""
        if server_name not in self._servers:
            print(f"⚠️ Server '{server_name}' not found or not running.")
            return None

        port = self._servers[server_name].get("port")
        base_url = f"http://127.0.0.1:{port}/mcp"
        args = args or {}

        import asyncio
        from fastmcp.client import Client

        async def _call():
            async with Client(base_url) as c:
                result = await c.call_tool(tool_name, args)
                await c.close()
                return result

        try:
            return asyncio.run(_call())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_call())




"""
from chatbot_widget.mcp.server_manager import MCPServerManager

mcp = MCPServerManager()

mcp.start("random", "src/chatbot_widget/mcp/random_server.py", port=8765)

# view logs directly in notebook
mcp.show_logs("random", n=15)

mcp.stop("random")



"""