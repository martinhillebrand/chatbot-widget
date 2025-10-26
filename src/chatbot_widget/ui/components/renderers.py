import ipywidgets as widgets
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
import json

def render_code(code: str, lang: str = "python") -> widgets.HTML:
    html = markdown(
        f"```{lang}\n{code}\n```",
        extensions=["fenced_code", CodeHiliteExtension(noclasses=True, pygments_style="default")],
    )
    return widgets.HTML(value=html)

def render_json(obj) -> widgets.HTML:
    code = f"```json\n{json.dumps(obj, indent=2)}\n```"
    html = markdown(code, extensions=["fenced_code", "codehilite"])
    return widgets.HTML(value=f"<div style='background:#f6f8fa;padding:8px;border-radius:6px'>{html}</div>")

def collapsible(title: str, content_html: str) -> widgets.HTML:
    return widgets.HTML(
        value=f"<details style='margin:4px 0;'><summary style='cursor:pointer;font-weight:bold;'>{title}</summary>{content_html}</details>"
    )
