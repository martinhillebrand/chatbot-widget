import re
import ipywidgets as widgets
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension


_DISALLOWED_TAGS = ("script", "iframe", "object", "embed")


def _sanitize_html(html: str) -> str:
    """Remove unsafe elements and attributes while keeping SVG content intact."""
    # remove disallowed blocks entirely
    pattern = r"<\s*({tags})\b[^>]*>.*?<\s*/\s*\1\s*>".format(tags="|".join(_DISALLOWED_TAGS))
    html = re.sub(pattern, "", html, flags=re.IGNORECASE | re.DOTALL)

    # strip event handlers (onclick, onload, ...)
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*\"[^\"]*\"", "", html)
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*'[^']*'", "", html)
    html = re.sub(r"\s+on[a-zA-Z]+\s*=\s*[^\s>]+", "", html)

    # neutralise javascript: URLs
    html = re.sub(r"javascript\s*:", "", html, flags=re.IGNORECASE)
    return html


class ChatBubble:
    """Single chat message bubble with subtle gradient and animation."""

    def __init__(self, text: str, sender: str = "bot"):
        self.sender = sender
        self.widget = widgets.HTML()
        self.update_text(text)

    def update_text(self, text: str):
        """Update the bubble contents (used for streaming responses)."""
        html = markdown(
            text,
            extensions=["fenced_code", "tables", CodeHiliteExtension(noclasses=True, pygments_style="default")],
        )
        html = _sanitize_html(html)

        if self.sender == "user":
            bg = "linear-gradient(135deg, #fff4e5 0%, #ffe1b3 100%)"
            align = "flex-end"
            border_radius = "18px 18px 4px 18px"
            text_color = "#3a2f00"
        else:
            bg = "linear-gradient(135deg, #f6f8fa 0%, #eaeef3 100%)"
            align = "flex-start"
            border_radius = "18px 18px 18px 4px"
            text_color = "#1a1a1a"

        self.widget.value = f"""
            <style>
            @keyframes cb-fade-in {{
                from {{ opacity: 0; transform: translateY(4px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            </style>
            <div style='display:flex;justify-content:{align};
                        margin:8px 0;
                        animation:cb-fade-in 0.2s ease-out;'>
              <div style='
                  background:{bg};
                  color:{text_color};
                  padding:0px 14px;
                  border-radius:{border_radius};
                  max-width:90%;
                  overflow-x:auto;
                  box-shadow:0 4px 10px rgba(0,0,0,0.08);
                  font-family:"Segoe UI","Helvetica Neue",Arial,sans-serif;
                  font-size:15px;
                  line-height:1.2;
                  margin: 0;
              '>
                {html}
              </div>
            </div>
        """
