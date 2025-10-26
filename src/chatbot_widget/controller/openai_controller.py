from openai import OpenAI


class OpenAIController:
    """OpenAI-backed conversational controller with simple command support."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self._on_response = None
        self.client = OpenAI()
        self.model = model
        self.history = []  # maintain chat context (list of dicts)

    # ---------------------------------------------------------------
    # Observer registration
    # ---------------------------------------------------------------
    def on_response(self, callback):
        """Register callback for responses back to the UI."""
        self._on_response = callback

    # ---------------------------------------------------------------
    # Main entrypoint
    # ---------------------------------------------------------------
    def handle_input(self, msg: str):
        """Handle a new user message or command."""
        if not msg.strip():
            return

        if msg.startswith("/"):
            reply = self._execute_command(msg.strip())
            if self._on_response:
                self._on_response(reply)
            return

        # Add user message to history
        self.history.append({"role": "user", "content": msg})

        # Send to OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
            )
            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})

            if self._on_response:
                self._on_response(reply)

        except Exception as e:
            if self._on_response:
                self._on_response(f"⚠️ Error: {e}")

    # ---------------------------------------------------------------
    # Command handler
    # ---------------------------------------------------------------
    def _execute_command(self, command: str):
        """Handle /clear, /help, /context commands."""
        cmd = command.lower().strip()

        if cmd in ("/clear", "/reset"):
            self.history.clear()
            return "🧹 Conversation history cleared."

        elif cmd in ("/help", "/?"):
            return (
                "**Available commands:**\n\n"
                "- `/help`: show this help\n"
                "- `/clear`: clear conversation\n"
                "- `/context`: show stored conversation\n"
            )

        elif cmd == "/context":
            if not self.history:
                return "_(no context stored)_"

            # build formatted markdown with light-blue horizontal lines
            formatted_blocks = []
            for m in self.history[-5:]:
                role = m["role"].capitalize()
                content = m["content"].strip()
                block = f"**{role}:**\n\n{content}"
                formatted_blocks.append(block)

            # join with styled horizontal rules
            separator = '<hr style="border:none;border-top:1px solid #a8c7ff;margin:6px 0;">'
            joined = f"\n{separator}\n".join(formatted_blocks)

            return f"🧠 **Current context (last 5):**\n\n{joined}"


        else:
            return f"❓ Unknown command: `{command}`"
