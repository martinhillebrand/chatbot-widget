import subprocess, sys, os, socket, random, time, json, asyncio
from fastmcp.client import Client
from chatbot_widget.utils.utils import run_async


class MCPServerManager:
    """Utility to start/stop FastMCP servers from notebooks or scripts, returning structured info."""

    def __init__(self):
        self._servers = {}

    def _find_free_port(self, start: int = 8600, end: int = 8900):
        for _ in range(50):
            port = random.randint(start, end)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free port available in range 8600–8900.")

    def start(self, name: str, script_path: str, port: int | None = None, log_file: str = None, **kwargs):
        if name in self._servers:
            return {"status": "error", "message": f"Server '{name}' already running."}

        script_path = os.path.abspath(script_path)
        if not os.path.exists(script_path):
            return {"status": "error", "message": f"Script not found: {script_path}"}

        port = port or self._find_free_port()
        log_file = log_file or f"{name}_server.log"
        f = open(log_file, "w", encoding="utf-8")

        extra_args = []
        for k, v in kwargs.items():
            extra_args.append(f"--{k}")
            if v not in (None, True):
                extra_args.append(str(v))

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
            "script_path": script_path,
        }

        time.sleep(2)
        healthy = self.check_health(name, port)
        return {
            "status": "ok" if healthy else "warning",
            "message": f"Started '{name}' on port {port} (PID={proc.pid})",
            "healthy": healthy,
            "port": port,
            "log_file": log_file,
        }

    def stop(self, name: str):
        if name not in self._servers:
            return {"status": "error", "message": f"No server named '{name}' found."}

        info = self._servers[name]
        proc = info["proc"]
        port = info.get("port")

        if proc.poll() is not None:
            self._servers.pop(name)
            return {"status": "ok", "message": f"Process for '{name}' already stopped."}

        try:
            proc.terminate()
            proc.wait(timeout=3)
            info["file"].close()
            self._servers.pop(name)
            return {"status": "ok", "message": f"Stopped '{name}' (port={port}, PID={proc.pid})."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop_all(self):
        if not self._servers:
            return {"status": "ok", "message": "No servers running."}
        results = [self.stop(name) for name in list(self._servers.keys())]
        return results

    def show_logs(self, name: str, n: int = 80, remove_windows_warnings: bool = True):
        log_file = self._servers.get(name, {}).get("log_file", f"{name}_server.log")
        if not os.path.exists(log_file):
            return {"status": "error", "message": f"No logs found for '{name}'."}

        try:
            with open(log_file, "r") as f:
                lines = f.readlines()[-n:]
            if remove_windows_warnings:
                lines = self._filter_logs(lines)
            return {"status": "ok", "lines": lines, "log_file": log_file}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _filter_logs(self, lines: list[str]) -> list[str]:
        LOG_PREFIXES = ("INFO:", "WARNING:", "ERROR:", "DEBUG:")
        NOISE_TRIGGERS = (
            "[WinError 10054]",
            "ConnectionResetError",
            "_ProactorBasePipeTransport._call_connection_lost",
        )
        filtered, skipping = [], False
        for line in lines:
            if not skipping:
                if any(t in line for t in NOISE_TRIGGERS):
                    skipping = True
                    continue
                filtered.append(line)
            else:
                if line.lstrip().startswith(LOG_PREFIXES):
                    skipping = False
                    filtered.append(line)
        compact, prev_blank = [], False
        for ln in filtered:
            if ln.strip() or not prev_blank:
                compact.append(ln)
            prev_blank = not ln.strip()
        return compact

    def check_health(self, name: str, port: int | None = None):
        if name not in self._servers and not port:
            return False
        port = port or self._servers[name].get("port")
        base_url = f"http://127.0.0.1:{port}"

        async def _check():
            async with Client(f"{base_url}/mcp") as c:
                await c.ping()
                await c.close()
                return True

        try:
            return run_async(_check())
        except Exception:
            return False

    def check_all(self):
        if not self._servers:
            return {"status": "ok", "message": "No servers running."}
        results = {}
        for name, info in self._servers.items():
            results[name] = self.check_health(name, info.get("port"))
        return results

    def list_tools(self, name: str, port: int | None = None):
        if name not in self._servers and not port:
            return []
        port = port or self._servers[name].get("port")
        base_url = f"http://127.0.0.1:{port}/mcp"

        async def _list():
            async with Client(base_url) as c:
                tools = await c.list_tools()
                await c.close()
                return tools

        return run_async(_list())

    def get_tool_server_dict(self):
        result = {}
        for server_name in self._servers.keys():
            tools = self.list_tools(server_name)
            for tool in tools:
                result[tool.name] = server_name
        return result

    def get_server_port_dict(self):
        return {s: info.get("port") for s, info in self._servers.items()}

    def test_tool(self, server_name: str, tool_name: str, args: dict | None = None):
        if server_name not in self._servers:
            return {"status": "error", "message": f"Server '{server_name}' not running."}

        port = self._servers[server_name].get("port")
        base_url = f"http://127.0.0.1:{port}/mcp"
        args = args or {}

        async def _call():
            async with Client(base_url) as c:
                result = await c.call_tool(tool_name, args)
                await c.close()
                return result

        try:
            result = run_async(_call())
            return {"status": "ok", "result": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_example_servers(self):
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example_server")
        if not os.path.exists(base_dir):
            return []
        server_files = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith("_server.py"):
                    path = os.path.abspath(os.path.join(root, f)).replace("\\", "/")
                    server_files.append(path)
        return server_files
