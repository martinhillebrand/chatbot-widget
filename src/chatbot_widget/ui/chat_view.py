import ipywidgets as widgets
from IPython.display import display, HTML
from .components.chat_bubble import ChatBubble
from .components.input_bar import InputBar
from .components.scroll_box import ScrollBox


class ChatView:
    """Main chat UI (publisher/subscriber pattern)."""

    def __init__(self):
        # Core UI components
        self.chat_box = ScrollBox()
        self.input_bar = InputBar()

        # Observer callbacks
        self._on_send_callback = None
        self._on_receive_callback = None
        self._on_response = None  # callback to UI

        # Layout
        self.container = widgets.VBox(
            [self.chat_box, self.input_bar.widget],
            layout=widgets.Layout(
                align_items="center",
                width="100%",
                max_width="900px",
                height="auto",
                overflow="visible",
                margin="0 auto",
                padding="20px",
                border="none",
                flex_flow="column",
                background="#c3c5c9",
                border_radius="12px",
            ),
        )

        # Welcome message
        welcome = widgets.HTML(
            "<div style='text-align:center;color:#555;padding:12px;'>"
            "💬 <b>Welcome! How can I help you today?</b></div>"
        )
        self.chat_box.children = (welcome,)

        # Hook input button to handler
        self.input_bar.button.on_click(self._handle_send)

        # Inject small CSS tweak to prevent notebook scroll
        display(HTML("""
        <style>
        .jp-OutputArea-output, .jp-OutputArea-child, .widget-html-content {
            overflow: visible !important;
            max-height: none !important;
        }
        </style>
        """))

    # ------------------------------------------------------------------ #
    # Observer registration
    # ------------------------------------------------------------------ #
    def on_send(self, callback):
        """Register callback(msg: str) when user sends a message."""
        self._on_send_callback = callback

    def on_receive(self, callback):
        """Register callback(text: str, sender: str) to show responses."""
        self._on_receive_callback = callback

    # ------------------------------------------------------------------ #
    # Internal event handling
    # ------------------------------------------------------------------ #
    def _handle_send(self, _=None):
        """Triggered when user clicks send."""
        text = self.input_bar.input.value.strip()
        if not text:
            return

        # Display user message immediately
        self.chat_box.children += (ChatBubble(text, sender="user").widget,)
        self.input_bar.clear()

        # Notify subscribers (e.g., controller)
        if self._on_send_callback:
            self._on_send_callback(text)

    # ------------------------------------------------------------------ #
    # Public display / response methods
    # ------------------------------------------------------------------ #
    def receive_message(self, text: str, sender="bot"):
        """Display a message (from controller)."""
        self.chat_box.children += (ChatBubble(text, sender).widget,)

    def display(self):
        """Render chat UI in the notebook."""
        display(self.container)
