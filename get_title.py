#!/usr/bin/env python3
"""Generate webpage title from URL."""

import re
import sys
from datetime import datetime

def get_webpage_title(url: str) -> str:
    import re
    from datetime import datetime
    # Remove query parameters and fragments first
    url = url.split('?')[0].split('#')[0].rstrip('/')
    # Split by / and get the last non-empty part
    parts = [part for part in url.split('/') if part]
    if parts:
        last_part = parts[-1]
        title = re.sub(r'[^a-zA-Z0-9]', '-', last_part).strip('-')
        base_title = title[:50] if title else "webpage"
    else:
        base_title = "webpage"
    
    # Add date prefix
    now = datetime.now()
    date_prefix = f"{now.day:02d}-{now.month:02d}-"
    return date_prefix + base_title

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_title.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    title = get_webpage_title(url)
    print(title)
