import warnings

import ipywidgets as widgets


class InputBar:
    """Text input + send button row with inline styling."""

    def __init__(self):
        style = widgets.HTML(
            value="""
<style>
.cbw-container { width: 100%; box-sizing: border-box; }

.cbw-bar {
  width: 100%;
  max-width: 720px;
  background: linear-gradient(135deg, #ffffff 0%, #f1f3ff 100%);
  border-radius: 22px;
  padding: 16px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

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

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            input_layout = widgets.Layout(
                flex="1",
                width="100%",
                border="none",
                overflow="hidden",
            )
            send_layout = widgets.Layout(width="52px", height="52px", border_radius="50%")
            bar_layout = widgets.Layout(
                justify_content="center",
                align_items="center",
                width="100%",
                padding="12px",
                gap="12px",
            )
            outer_layout = widgets.Layout(align_items="center", width="100%")

        self.input = widgets.Textarea(
            placeholder="Type a message… \nor use /help to see available commands",
            rows=3,
            layout=input_layout,
        )
        self.input.add_class("cbw-input")

        self.button = widgets.Button(
            icon="arrow-up",
            tooltip="Send",
            layout=send_layout,
        )
        self.button.add_class("cbw-send")

        bar = widgets.HBox([self.input, self.button], layout=bar_layout)
        bar.add_class("cbw-bar")

        self.widget = widgets.VBox([style, bar], layout=outer_layout)

    def clear(self):
        self.input.value = ""

    def set_busy(self, busy: bool):
        """Toggle busy state (disables the send button)."""
        self.button.disabled = busy
