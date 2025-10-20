"""
Teradata SQL MCP Server
-----------------------

Usage examples:

# --- Run from command line ---
python teradatasql_server.py 8800 --host mydb.teradata.com --username alice --password secret

# --- Run from MCPServerManager ---
mcp.start(
    "teradata",
    "src/chatbot_widget/mcp/teradatasql_server.py",
    port=8800,
    host="mydb.teradata.com",
    username="alice",
    password="secret"
)
"""

from fastmcp import FastMCP
import teradatasql
import argparse
import sys

mcp = FastMCP("Teradata SQL MCP Server")

# --- Global connection state ---
conn = None
db_host = None
db_user = None
db_pass = None


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------
def _connect():
    """(Re)connect to the Teradata database."""
    global conn, db_host, db_user, db_pass
    try:
        conn = teradatasql.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
        )
        return "Connected successfully."
    except Exception as e:
        conn = None
        return f"Connection failed: {e}"


def _disconnect():
    """Close existing connection."""
    global conn
    if conn:
        try:
            conn.close()
            conn = None
            return "Disconnected from database."
        except Exception as e:
            return f"Error while disconnecting: {e}"
    else:
        return "No active connection."


# ------------------------------------------------------------------
# Tools
# ------------------------------------------------------------------
@mcp.tool("ping")
def ping() -> str:
    """Test the database connection by executing a trivial query."""
    global conn
    if not conn:
        return "Not connected. Use `connect` first."

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1+1 AS mysum;")
            row = cur.fetchone()
            return f"Database responded: mysum = {row[0]}"
    except Exception as e:
        return f"Ping failed: {e}"


@mcp.tool("connect")
def connect_tool() -> str:
    """Reconnect to the database."""
    return _connect()


@mcp.tool("disconnect")
def disconnect_tool() -> str:
    """Disconnect from the database."""
    return _disconnect()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Teradata MCP Server.")
    parser.add_argument("port", type=int, help="MCP server port.")
    parser.add_argument("--host", required=True, help="Teradata host.")
    parser.add_argument("--username", required=True, help="Teradata username.")
    parser.add_argument("--password", required=True, help="Teradata password.")
    args = parser.parse_args()

    db_host, db_user, db_pass = args.host, args.username, args.password

    print("Connecting to Teradata...")
    msg = _connect()
    print(msg)

    if msg.startswith("Connection failed"):
        print("Cannot start MCP - database connection failed.")
        sys.exit(1)

    print("Starting Teradata MCP Server...")
    mcp.run(transport="http", port=args.port)
