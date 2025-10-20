"""
Random Number MCP Server
------------------------

Usage examples:

# --- Run directly from command line ---
python random_server.py 8765 --seed 42

# --- Or launch from MCPServerManager ---
mcp.start(
    "random",
    "src/chatbot_widget/mcp/random_server.py",
    port=8765,
    seed=42 # optional
)
"""

import argparse
import random
from fastmcp import FastMCP

mcp = FastMCP("My Random Number MCP Server")


@mcp.tool("numbers")
def generate_random_numbers(count: int = 5, min_value: int = 0, max_value: int = 100) -> list[int]:
    """Generate a list of random integers."""
    if count < 1:
        raise ValueError("Count must be at least 1")
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value")
    return [random.randint(min_value, max_value) for _ in range(count)]


@mcp.tool("greet")
def greet() -> str:
    """Returns a friendly greeting."""
    return "Hello!"


if __name__ == "__main__":
    # --- Parse command-line arguments ---
    parser = argparse.ArgumentParser(description="Start the Random Number MCP Server.")
    parser.add_argument("port", type=int, help="Port number for the MCP server.")
    parser.add_argument("--seed", type=int, help="Optional random seed (integer).")
    args = parser.parse_args()

    # --- Apply random seed if provided ---
    if args.seed is not None:
        random.seed(args.seed)        

    # --- Start the MCP server ---
    mcp.run(transport="http", port=args.port)
