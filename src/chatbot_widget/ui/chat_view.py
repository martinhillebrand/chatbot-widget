import ipywidgets as widgets
from IPython.display import display, HTML
from .components.chat_bubble import ChatBubble
from .components.input_bar import InputBar
from .components.scroll_box import ScrollBox
from .components.renderers import render_code, render_json, collapsible



class ChatView:
    """Main chat UI layout (purely presentation)."""


    def __init__(self):


        self.chat_box = ScrollBox()
        self.input_bar = InputBar()
        self.input_bar.button.on_click(self._handle_send)


        self.container = widgets.VBox(
            [self.chat_box, self.input_bar.widget],
            layout=widgets.Layout(
                align_items="center",
                width="100%",
                max_width="900px",     # ✅ limit overall chat width
                height="auto",
                overflow="visible",
                margin="0 auto",       # ✅ center horizontally
                padding="20px",        # ✅ small breathing space
                border="none",
                flex_flow="column",
                background="#c3c5c9",  # ✅ subtle light blue background
                border_radius="12px",  # optional for softer edges
            ),
        )

        welcome = widgets.HTML(
            "<div style='text-align:center;color:#888;padding:12px;'>"
            "💬 <b>Welcome! How can I help you today?</b></div>"
        )
        self.chat_box.children = (welcome,)

        
        display(HTML("""
        <style>
        /* remove notebook scroll on widget output */
        .jp-OutputArea-output, .jp-OutputArea-child, .widget-html-content {
            overflow: visible !important;
            max-height: none !important;
        }
        </style>
        """))




    # --- internal methods ---
    def _handle_send(self, _=None):
        print("i am in send")
        text = self.input_bar.input.value.strip()
        if not text:
            return
        self.chat_box.children += (ChatBubble(text, sender="user").widget,)
        self.input_bar.clear()
        for w in self._respond(text):
            self.chat_box.children += (w,)

    def _respond(self, msg: str):
        print("i am in respond")
        msg_str = msg.strip()
        m = msg_str.lower()
        outputs = []

        if m.startswith("python"):
            code = """def hello_world():
        print("Hello, world!")"""
            content = render_code(code, "python").value
            outputs.append(ChatBubble(content, sender="bot").widget)

        elif m.startswith("sql"):
            code = """SELECT name, age
    FROM users
    WHERE active = TRUE
    ORDER BY age DESC;"""
            content = render_code(code, "sql").value
            outputs.append(ChatBubble(content, sender="bot").widget)

        elif "json" in m:
            data = {"result": 4, "status": "ok"}
            content = collapsible("JSON result", render_json(data).value).value
            outputs.append(ChatBubble(content, sender="bot").widget)

        elif "hello" in m:
            outputs.append(ChatBubble("👋 **Hey there!**", sender="bot").widget)

        else:
            outputs.append(ChatBubble(f"Echo: `{msg_str}`", sender="bot").widget)

        return outputs



    # --- public methods ---
    def display(self):
        display(self.container)
