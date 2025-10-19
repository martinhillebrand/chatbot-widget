import ipywidgets as widgets

class InputBar:
    """Text input + send button row with inline CSS (self-contained like ChatBubble)."""

    def __init__(self):
        # inline CSS lives with the widget (no external modules needed)
        style = widgets.HTML(
            value="""
<style>
/* container */
.cbw-container { width: 100%; box-sizing: border-box; }

/* pretty bar */
.cbw-bar {
  width: 100%;
  max-width: 720px;
  background: linear-gradient(135deg, #ffffff 0%, #f1f3ff 100%);
  border-radius: 22px;
  padding: 16px;
  box-sizing: border-box;
}

/* textarea inside the input widget */
.cbw-input textarea {
  font-family: "Segoe UI","Helvetica Neue",Arial,sans-serif;
  font-size: 15px;
  line-height: 1.5;
  color: #2b275a;
  border: none !important;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(108,99,255,0.18);
  padding: 14px 18px;
  border-radius: 16px;
  transition: box-shadow .2s ease, background-color .2s ease;
  min-height: 90px;
}
.cbw-input textarea:focus {
  outline: none !important;
  background-color: #f6f5ff;
  box-shadow: inset 0 0 0 2px rgba(108,99,255,0.35);
}

/* button styling */
.cbw-send .widget-button {
  border: none;
  color: #ffffff;
  background: linear-gradient(135deg, #6c63ff, #8573ff);
  border-radius: 50%;
  box-shadow: 0 12px 24px rgba(108,99,255,0.28);
  font-size: 18px;
  transition: transform .15s ease, box-shadow .15s ease;
  width: 52px; height: 52px;
}
.cbw-send .widget-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 28px rgba(108,99,255,0.32);
}
.cbw-send .widget-button:focus {
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(108,99,255,0.25);
}
</style>
"""
        )

        self.input = widgets.Textarea(
            placeholder="Type a message… \nor use /help to see available commands",
            rows=3,
            layout=widgets.Layout(
                flex="1",
                width="100%",
                border="none",
                overflow="hidden",
            ),
        )
        self.input.add_class("cbw-input")

        self.button = widgets.Button(
            icon="arrow-up",
            tooltip="Send",
            layout=widgets.Layout(width="52px", height="52px", border_radius="50%"),
        )
        self.button.add_class("cbw-send")

        bar = widgets.HBox(
            [self.input, self.button],
            layout=widgets.Layout(
                justify_content="center",
                align_items="center",
                width="100%",
                padding="12px",
                gap="12px",
            ),
        )
        bar.add_class("cbw-bar")

        self.widget = widgets.VBox([style, bar], layout=widgets.Layout(align_items="center", width="100%"))

    def clear(self):
        self.input.value = ""
