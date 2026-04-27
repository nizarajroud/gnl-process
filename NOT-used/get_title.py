#!/usr/bin/env python3
"""Generate webpage title from URL."""

import re
import sys
from datetime import datetime
import os

def get_webpage_title(sourceIdentifier: str, type: str = "URL", subsuffix: str = None) -> str:
    import re
    from datetime import datetime
    
    if type in ["GoogleDrive", "LocalStorage"]:
        base_title = os.path.splitext(os.path.basename(sourceIdentifier))[0]
        if subsuffix:
            return f"{base_title}-{subsuffix}"
        return base_title
    else:  # WebAndYoutube, youtube, copied-text
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
        
        if subsuffix:
            return f"{base_title}-{subsuffix}"
    
    # Add date prefix for non-GoogleDrive/LocalStorage types
    now = datetime.now()
    date_prefix = f"{now.day:02d}-{now.month:02d}-"
    return date_prefix + base_title

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage: python get_title.py <sourceIdentifier> [type] [subsuffix]")
        print("Types: WebAndYoutube (default), GoogleDrive, LocalStorage")
        print("subsuffix: Optional suffix to append")
        sys.exit(1)
    
    sourceIdentifier = sys.argv[1]
    type = sys.argv[2] if len(sys.argv) >= 3 else "WebAndYoutube"
    subsuffix = sys.argv[3] if len(sys.argv) == 4 else None
    title = get_webpage_title(sourceIdentifier, type, subsuffix)
    print(title)
