import ipywidgets as widgets
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension

class ChatBubble:
    """Single chat message bubble with subtle gradient and animation."""

    def __init__(self, text: str, sender: str = "bot"):
        html = markdown(
            text,
            extensions=["fenced_code", "tables", CodeHiliteExtension(noclasses=True, pygments_style="default")]
        )

        if sender == "user":
            bg = "linear-gradient(135deg, #fff4e5 0%, #ffe1b3 100%)"
            align = "flex-end"
            border_radius = "18px 18px 4px 18px"
            text_color = "#3a2f00"
        else:
            bg = "linear-gradient(135deg, #f6f8fa 0%, #eaeef3 100%)"
            align = "flex-start"
            border_radius = "18px 18px 18px 4px"
            text_color = "#1a1a1a"

        self.widget = widgets.HTML(
            value=f"""
            <style>
            @keyframes cb-fade-in {{
                from {{ opacity: 0; transform: translateY(4px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            </style>
            <div style='display:flex;justify-content:{align};
                        margin:8px 0;  /* ↓ tighter vertical spacing */
                        animation:cb-fade-in 0.2s ease-out;'>
              <div style='
                  background:{bg};
                  color:{text_color};
                  padding:0px 14px;  /* ↓ slightly reduced padding */
                  border-radius:{border_radius};
                  max-width:90%;     /* ✅ limit bubble width */
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
        )
