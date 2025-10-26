import warnings

import ipywidgets as widgets


class ScrollBox(widgets.VBox):
    """Container for chat bubbles without any internal scroll."""

    def __init__(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            layout = widgets.Layout(
                padding="10px",
                border_radius="10px",
                width="90%",
                margin="0",
                background="#646e7e",
                overflow="visible",
                height="auto",
                max_height=None,
            )
        super().__init__(layout=layout)
