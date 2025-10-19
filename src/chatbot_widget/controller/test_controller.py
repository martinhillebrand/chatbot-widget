class TestController:
    """Simple controller for testing ChatView integration."""

    def __init__(self):
        self._on_response = None  # callback to UI

    # ---------------------------------------------------------------
    # Observer registration
    # ---------------------------------------------------------------
    def on_response(self, callback):
        """Register a callback that receives bot messages."""
        self._on_response = callback

    # ---------------------------------------------------------------
    # Message handling
    # ---------------------------------------------------------------
    def handle_input(self, msg: str):
        """Called when user sends a message."""
        msg = msg.strip().lower()

        if msg.startswith("python"):
            reply = (
                "Here's some Python code:\n"
                "```python\n"
                "def hello_world():\n"
                "    print('Hello, world!')\n"
                "```"
            )
        elif msg.startswith("sql"):
            reply = (
                "Example SQL query:\n"
                "```sql\n"
                "SELECT * FROM users LIMIT 5;\n"
                "```"
            )
        elif "json" in msg:
            reply = (
                "Sample JSON:\n"
                "```json\n"
                "{\n  \"status\": \"ok\",\n  \"value\": 42\n}\n"
                "```"
            )
        elif "hello" in msg:
            reply = "👋 Hey there!"
        else:
            reply = f"Echo: {msg}"

        # Publish back to UI if subscribed
        if self._on_response:
            self._on_response(reply)
