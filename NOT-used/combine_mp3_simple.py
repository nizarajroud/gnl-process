#!/usr/bin/env python3
"""Concatenate MP3 files alphabetically."""

import subprocess
import sys
from pathlib import Path

def convert_windows_to_wsl_path(path: str) -> str:
    if ':' in path:
        path = path.replace('\\', '/')
        drive = path[0].lower()
        rest = path[2:] if len(path) > 2 else ''
        return f'/mnt/{drive}{rest}'
    return path

def main(folder: str):
    folder = convert_windows_to_wsl_path(folder)
    folder_path = Path(folder)
    if not folder_path.exists():
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)
    
    mp3_files = sorted(folder_path.glob("*.mp3"))
    if not mp3_files:
        print(f"No MP3 files found in {folder}")
        sys.exit(1)
    
    print(f"Found {len(mp3_files)} MP3 files")
    
    # Extract base name from first file (remove trailing number)
    import re
    base_name = re.sub(r'-?\d+$', '', mp3_files[0].stem)
    
    list_file = folder_path / "concat_list.txt"
    with open(list_file, "w") as f:
        for file in mp3_files:
            f.write(f"file '{file.absolute()}'\n")
    
    output_file = folder_path / f"{base_name}.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
        "-i", str(list_file), "-c", "copy", str(output_file)
    ], check=True)
    
    list_file.unlink()
    print(f"\n✓ Combined file: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python combine_mp3_simple.py <folder_path>")
        sys.exit(1)
    
    main(' '.join(sys.argv[1:]))
