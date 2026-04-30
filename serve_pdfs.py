#!/usr/bin/env python3
"""Serve PDF-Parts folder over HTTP for NotebookLM URL-based upload.

Usage:
    python serve_pdfs.py [--port=8000]
"""

import os
import http.server
import functools
import fire
from dotenv import load_dotenv

load_dotenv()


def main(port: int = None):
    port = port or int(os.getenv('PDF_SERVER_PORT', '8000'))
    directory = os.getenv('PDF_PARTS_FOLDER')
    if not directory:
        raise ValueError("PDF_PARTS_FOLDER must be set in .env")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    server = http.server.HTTPServer(('0.0.0.0', port), handler)
    print(f"Serving {directory} on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    fire.Fire(main)
