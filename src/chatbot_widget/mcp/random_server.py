from fastmcp import FastMCP
import random

mcp = FastMCP("My Random Number MCP Server")

@mcp.tool("numbers")
def generate_random_numbers(count: int = 5, min_value: int = 0, max_value: int = 100):
    """ Generate a list of random integers."""
    if count < 1:
        raise ValueError("Count must be at least 1")
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value")

    return [random.randint(min_value, max_value) for _ in range(count)]

@mcp.tool("greet")
def greet() -> str:
    return f"Hello!"

if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="http", port=8765)


"""
Instructions: (also works on CSAE)
- run this server like
python random_server.py

in a notebook you can use this to test

import asyncio
from fastmcp import Client

client = Client("http://localhost:8765/mcp")

async def call_tool(name: str):
    async with client:
        result = await client.call_tool("greet")
        print(result)

async def call_numbers():
    async with client:
        result = await client.call_tool("numbers",dict(count= 5, min_value = 0, max_value=20))
        print(result)
        
asyncio.run(call_tool("Ford"))
asyncio.run(call_numbers())

async with client:
    tools = await client.list_tools()
    # tools -> list[mcp.types.Tool]
    
    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description}")
        if tool.inputSchema:
            print(f"Parameters: {tool.inputSchema}")
        # Access tags and other metadata
        if hasattr(tool, 'meta') and tool.meta:
            fastmcp_meta = tool.meta.get('_fastmcp', {})
            print(f"Tags: {fastmcp_meta.get('tags', [])}")


            
# and to run it in a jupyter notbeook

import subprocess, sys

# Path to your MCP server script
server_script = "random_server.py"

# Where to store logs
log_file = "mcp_server_random.log"

# Launch the MCP server silently
proc = subprocess.Popen(
    [sys.executable, server_script],
    stdout=open(log_file, "w"),
    stderr=subprocess.STDOUT,
)
print(f"MCP server started (PID={proc.pid}). Logs -> {log_file}")



proc.terminate()  # or proc.kill()
print("MCP server stopped.")


"""