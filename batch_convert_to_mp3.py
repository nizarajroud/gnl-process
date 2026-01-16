#!/usr/bin/env python3
"""Convert M4A file to MP3 format and remove original."""

import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv
import fire

load_dotenv()

def convert_m4a_to_mp3(filename: str, suffix: str, subsuffix: str):
    """Convert M4A to MP3 and delete original."""
    gnl_backlog = os.getenv('GNL_BACKLOG')
    if not gnl_backlog:
        raise ValueError("GNL_BACKLOG not found in .env file")
    
    # Add .m4a extension if not present
    if not filename.endswith('.m4a'):
        filename = f"{filename}.m4a"
    
    input_file = Path(gnl_backlog) / suffix / subsuffix / filename
    output_file = input_file.with_suffix('.mp3')
    
    subprocess.run(['ffmpeg', '-i', str(input_file), str(output_file)], check=True)
    os.remove(input_file)
    print(f"Converted and removed: {input_file} -> {output_file}")

if __name__ == "__main__":
    fire.Fire(convert_m4a_to_mp3)
