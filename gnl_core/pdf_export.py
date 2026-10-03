"""Render a Meta-AI-readable PDF from the Plan B markdown corpus.

Meta AI reliably extracts text from PDF (and Office) documents, but NOT from
raw .md attachments (it accepts them but "sees nothing"). So Plan B writes a
PDF by default. We convert the markdown corpus to simple HTML, then to PDF with
WeasyPrint (already in requirements, works with the system Python).
"""
from pathlib import Path


def write_pdf(markdown_text, out_path, title=None):
    """Convert `markdown_text` to a PDF at `out_path`. Returns str(out_path).

    Falls back cleanly: markdown -> HTML (python-markdown) -> PDF (WeasyPrint).
    """
    import markdown as _md
    from weasyprint import HTML

    body_html = _md.markdown(
        markdown_text,
        extensions=['extra', 'sane_lists', 'nl2br'],
    )
    safe_title = (title or 'Document')
    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:11pt;"
        "line-height:1.4;color:#111;margin:1.6cm;}"
        "h1{font-size:16pt;} h2{font-size:13pt;margin-top:1.1em;"
        "border-bottom:1px solid #ccc;padding-bottom:2px;}"
        "ul{margin:0.3em 0 0.6em 1.2em;} li{margin:0.15em 0;}"
        "code,pre{font-family:'DejaVu Sans Mono',monospace;font-size:10pt;}"
        "</style></head><body>"
        + body_html +
        "</body></html>"
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc).write_pdf(str(out))
    return str(out)
