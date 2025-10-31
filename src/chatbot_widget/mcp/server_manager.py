
import ast
import os
import random
import socket
import subprocess
import sys
import time

from fastmcp.client import Client
from chatbot_widget.utils.utils import run_async


class MCPServerManager:
    """High level orchestration helper for lightweight FastMCP servers.

    The manager keeps a registry of spawned Python scripts, exposes health and
    log inspection helpers, and provides several convenience utilities that play
    nicely inside notebooks.

    Examples
    --------
    >>> mgr = MCPServerManager()
    >>> mgr.start("random", "path/to/random_server.py", seed=42)
    {'status': 'ok', 'port': 8765, ...}
    >>> mgr.list_tools("random")
    [ToolInfo(name='numbers', ...), ToolInfo(name='greet', ...)]
    >>> mgr.stop_all()
    [{'status': 'ok', 'message': "Stopped 'random' (...)"}, ...]
    """

    def __init__(self):
        self._servers = {}

    def _find_free_port(self, start: int = 8600, end: int = 8900):
        """Return a free TCP port within the inclusive range ``[start, end]``.

        Parameters
        ----------
        start, end:
            Integer boundaries that roughly represent the preferred port range.

        Raises
        ------
        RuntimeError
            If no free port is found after 50 attempts.

        Examples
        --------
        >>> mgr = MCPServerManager()
        >>> port = mgr._find_free_port()
        >>> 8600 <= port <= 8900
        True
        """
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
        """Launch a FastMCP server script as a subprocess.

        Parameters
        ----------
        name:
            Friendly identifier used to reference the subprocess.
        script_path:
            Path to the Python file that defines the `FastMCP` application.
        port:
            Optional port override. If omitted a free port is selected.
        log_file:
            Optional path to the log file. Defaults to ``{name}_server.log``.
        **kwargs:
            Extra command-line arguments supplied as ``--key value`` pairs.

        Returns
        -------
        dict
            Structured result containing the status, message, port, and log file.

        Examples
        --------
        >>> mgr = MCPServerManager()
        >>> mgr.start("ascii", "mcp/example_server/ascii_server.py")
        {'status': 'ok', 'message': "Started 'ascii' on port ...", ...}
        """
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
        """Terminate a running server started via :meth:`start`.

        Parameters
        ----------
        name:
            Identifier supplied when the server was launched.

        Returns
        -------
        dict
            Status payload indicating whether termination succeeded.
        """
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
        """Terminate every tracked server and return individual results."""
        if not self._servers:
            return {"status": "ok", "message": "No servers running."}
        results = [self.stop(name) for name in list(self._servers.keys())]
        return results

    def show_logs(self, name: str, n: int = 80, remove_windows_warnings: bool = True):
        """Return the tail of the log file for ``name``.

        Parameters
        ----------
        name:
            Identifier supplied to :meth:`start`.
        n:
            Number of trailing lines to read.
        remove_windows_warnings:
            When ``True`` strips noisy Windows connection reset spam.

        Examples
        --------
        >>> mgr.show_logs("random", 20)
        {'status': 'ok', 'lines': [...], 'log_file': 'random_server.log'}
        """
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
        """Remove repetitive Windows `ConnectionResetError` noise from logs."""
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
        """Ping the MCP endpoint for ``name`` (or explicit ``port``) to verify it is healthy."""
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
        """Return a mapping of ``{server_name: bool}`` describing health for every running server."""
        if not self._servers:
            return {"status": "ok", "message": "No servers running."}
        results = {}
        for name, info in self._servers.items():
            results[name] = self.check_health(name, info.get("port"))
        return results

    def list_tools(self, name: str, port: int | None = None):
        """List all tools declared by a running MCP server."""
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
        """Return mapping ``{tool_name: server_name}`` for the active servers."""
        result = {}
        for server_name in self._servers.keys():
            tools = self.list_tools(server_name)
            for tool in tools:
                result[tool.name] = server_name
        return result

    def get_server_port_dict(self):
        """Return mapping ``{server_name: port}`` of active servers."""
        return {s: info.get("port") for s, info in self._servers.items()}

    def test_tool(self, server_name: str, tool_name: str, args: dict | None = None):
        """Execute an MCP tool with JSON-serialisable ``args`` and return the response."""
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
        """Return absolute paths to bundled example server scripts."""
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

    # ------------------------------------------------------------------
    # Documentation helpers
    # ------------------------------------------------------------------
    def show_server_source(self, name: str | None = None, script_path: str | None = None, *, include_line_numbers: bool = True):
        """Return the source code of a FastMCP server script.

        Parameters
        ----------
        name, script_path:
            Either supply the friendly ``name`` used with :meth:`start` or a
            direct ``script_path`` pointing to the Python file on disk.
        include_line_numbers:
            When ``True`` prefixes each line with a human friendly counter.

        Returns
        -------
        dict
            ``{'status': 'ok', 'path': str, 'source': str}`` on success.

        Examples
        --------
        >>> mgr.show_server_source(script_path=".../random_server.py")
        {'status': 'ok', 'path': '.../random_server.py', 'source': '1: import ...'}
        """
        path = self._resolve_script_path(name, script_path)
        if not path:
            return {"status": "error", "message": "Server not found."}
        if not os.path.exists(path):
            return {"status": "error", "message": f"Script not found: {path}"}

        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        if include_line_numbers:
            numbered = "\n".join(f"{idx+1:>4}: {line}" for idx, line in enumerate(content.splitlines()))
        else:
            numbered = content
        return {"status": "ok", "path": path, "source": numbered}

    def inspect_cli_arguments(self, name: str | None = None, script_path: str | None = None):
        """Inspect argparse configuration of a server script.

        The helper performs a lightweight static analysis to extract calls to
        ``parser.add_argument(...)`` and exposes the flags together with the
        keyword settings (help text, default values, etc).

        Parameters
        ----------
        name, script_path:
            Either the registered server name or an explicit path.

        Returns
        -------
        dict
            A payload containing ``status`` and ``arguments`` keys. Each
            argument entry is a dictionary with ``flags`` and ``options``.

        Examples
        --------
        >>> mgr.inspect_cli_arguments(script_path=".../random_server.py")
        {
            'status': 'ok',
            'arguments': [
                {'flags': ['port'], 'options': {'type': 'int', 'help': 'Port number...'}},
                {'flags': ['--seed'], 'options': {'type': 'int', 'help': 'Optional random seed...'}}
            ]
        }
        """
        path = self._resolve_script_path(name, script_path)
        if not path:
            return {"status": "error", "message": "Server not found."}
        if not os.path.exists(path):
            return {"status": "error", "message": f"Script not found: {path}"}

        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return {"status": "error", "message": f"Unable to parse script: {exc}"}

        arguments: list[dict[str, object]] = []

        class _ArgumentCollector(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call):  # noqa: N802
                if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
                    flags: list[str] = []
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            flags.append(arg.value)
                    if not flags:
                        # If first positional is not a string we skip (unlikely).
                        return

                    options: dict[str, str] = {}
                    for kw in node.keywords:
                        key = kw.arg or ""
                        if not key:
                            continue
                        value = _safe_unparse(kw.value)
                        options[key] = value

                    arguments.append({"flags": flags, "options": options})
                self.generic_visit(node)

        def _safe_unparse(node: ast.AST) -> str:
            if isinstance(node, ast.Constant):
                return repr(node.value)
            if isinstance(node, ast.Name):
                return node.id
            if hasattr(ast, "unparse"):
                return ast.unparse(node)  # type: ignore[attr-defined]
            return ast.dump(node)

        _ArgumentCollector().visit(tree)

        if not arguments:
            return {
                "status": "warning",
                "message": "No argparse configuration detected. The script may rely on manual sys.argv parsing.",
                "arguments": [],
            }

        return {"status": "ok", "path": path, "arguments": arguments}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_script_path(self, name: str | None, script_path: str | None) -> str | None:
        """Resolve a script path either from a running server name or an explicit value."""
        if script_path:
            return os.path.abspath(script_path)
        if name and name in self._servers:
            return self._servers[name].get("script_path")
        return None
