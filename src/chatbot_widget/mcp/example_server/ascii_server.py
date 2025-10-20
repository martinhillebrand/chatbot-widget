from fastmcp import FastMCP
import pyfiglet
import sys

mcp = FastMCP("ASCII Art MCP Server")

@mcp.tool("ascii_art")
def ascii_art(text: str):
    """Generate simple ASCII art for a short string (max 10 chars)."""
    if not text:
        raise ValueError("Text must not be empty.")
    if len(text) > 10:
        raise ValueError("Text too long (max 10 characters).")
    return pyfiglet.figlet_format(text, font="standard")

@mcp.tool("mirror")
def mirror_text(text: str):
    """Return text mirrored (reversed)."""
    if len(text) > 20:
        raise ValueError("Text too long (max 20 characters).")
    return text[::-1]

if __name__ == "__main__":
    port = 8770  # default port, override via CLI
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    mcp.run(transport="http", port=port)
