import ipywidgets as widgets

class ScrollBox(widgets.VBox):
    """Container for chat bubbles without any internal scroll."""
    def __init__(self):
        super().__init__(
            layout=widgets.Layout(
                padding="10px",
                border_radius="10px",
                width="90%",
                margin="0",                
                background="#646e7e",  # ✅ let outer background show through
                overflow="visible",   # ✅ never scroll
                height="auto",
                max_height=None,
            )
        )
