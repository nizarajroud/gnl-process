#!/usr/bin/env python3
"""Generate webpage title from URL."""

import re
import sys
from datetime import datetime
import os

def get_webpage_title(sourceIdentifier: str, type: str = "URL", subsuffix: str = None) -> str:
    import re
    from datetime import datetime
    
    if type == "FileUpload":
        # For file uploads, just get the filename without extension
        base_title = os.path.splitext(os.path.basename(sourceIdentifier))[0]
        # Add subsuffix instead of date for FileUpload
        if subsuffix:
            return f"{base_title}-{subsuffix}"
        return base_title
    elif type == "CopiedText":
        # For copied text, use first 50 characters, sanitized
        text_snippet = sourceIdentifier[:50]
        base_title = re.sub(r'[^a-zA-Z0-9]', '-', text_snippet).strip('-')
        if not base_title:
            base_title = "copied-text"
    else:  # URL
        # Remove query parameters and fragments first
        sourceIdentifier = sourceIdentifier.split('?')[0].split('#')[0].rstrip('/')
        # Split by / and get the last non-empty part
        parts = [part for part in sourceIdentifier.split('/') if part]
        if parts:
            last_part = parts[-1]
            title = re.sub(r'[^a-zA-Z0-9]', '-', last_part).strip('-')
            base_title = title[:50] if title else "webpage"
        else:
            base_title = "webpage"
    
    # Add date prefix for non-FileUpload types
    now = datetime.now()
    date_prefix = f"{now.day:02d}-{now.month:02d}-"
    return date_prefix + base_title

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage: python get_title.py <sourceIdentifier> [type] [subsuffix]")
        print("Types: URL (default), FileUpload, CopiedText")
        print("subsuffix: Optional, used with FileUpload type instead of date")
        sys.exit(1)
    
    sourceIdentifier = sys.argv[1]
    type = sys.argv[2] if len(sys.argv) >= 3 else "URL"
    subsuffix = sys.argv[3] if len(sys.argv) == 4 else None
    title = get_webpage_title(sourceIdentifier, type, subsuffix)
    print(title)
