#!/usr/bin/env python3
"""Concatenate multiple MP3 files into one."""

import sys
import os
from pathlib import Path
from pydub import AudioSegment
from dotenv import load_dotenv

load_dotenv()

def combine_mp3(directory, output_file):
    base_path = os.getenv('GNL_BACKLOG')
    if not base_path:
        print("Error: GNL_BACKLOG environment variable not set")
        sys.exit(1)
    
    full_path = Path(base_path) / directory
    mp3_files = sorted(full_path.glob("*.mp3"))
    if not mp3_files:
        print(f"No MP3 files found in {full_path}")
        sys.exit(1)
    
    output_path = full_path / output_file
    
    # Use ffmpeg to concatenate without loading all into memory
    import subprocess
    list_file = "concat_list.txt"
    with open(list_file, "w") as f:
        for file in mp3_files:
            print(f"Adding: {file.name}")
            f.write(f"file '{file.absolute()}'\n")
    
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", str(output_path)], check=True)
    os.remove(list_file)
    print(f"Combined {len(mp3_files)} files into {output_path}")
    
    # Move input files to ZZ folder
    zz_folder = full_path / "zz"
    zz_folder.mkdir(exist_ok=True)
    for file in mp3_files:
        file.rename(zz_folder / file.name)
    print(f"Moved {len(mp3_files)} files to {zz_folder}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python combine_mp3.py <subdirectory> <output.mp3>")
        sys.exit(1)
    
    directory = sys.argv[1]
    output_file = sys.argv[2]
    combine_mp3(directory, output_file)
