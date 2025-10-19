import subprocess, sys, os

class MCPServerManager:
    """Utility to start/stop FastMCP servers from notebooks."""

    def __init__(self):
        self._servers = {}

    def start(self, name: str, script_path: str, port: int, log_file: str = None):
        """Start MCP server silently in background."""
        if name in self._servers:
            print(f"⚠️ Server '{name}' already running.")
            return

        log_file = log_file or f"{name}_server.log"
        f = open(log_file, "w")

        proc = subprocess.Popen(
            [sys.executable, script_path, str(port)],
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
        )

        self._servers[name] = {"proc": proc, "file": f, "log_file": log_file}
        print(f"✅ Started '{name}' on port {port} (PID={proc.pid}) → logs: {log_file}")

    def stop(self, name: str):
        """Stop a named MCP server."""
        if name not in self._servers:
            print(f"⚠️ No server named '{name}' found.")
            return

        info = self._servers.pop(name)
        proc = info["proc"]
        f = info["file"]
        proc.terminate()
        proc.wait(timeout=3)
        f.close()
        print(f"🛑 Stopped server '{name}'.")

    def stop_all(self):
        """Stop all running MCP servers."""
        for name in list(self._servers.keys()):
            self.stop(name)

    def show_logs(self, name: str, n: int = 20):
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
            print(f"\n📜 Last {n} lines from {log_file}:\n" + "".join(lines))
        except Exception as e:
            print(f"⚠️ Could not read logs: {e}")


"""
from chatbot_widget.mcp.server_manager import MCPServerManager

mcp = MCPServerManager()

mcp.start("random", "src/chatbot_widget/mcp/random_server.py", port=8765)

# view logs directly in notebook
mcp.show_logs("random", n=15)

mcp.stop("random")



"""