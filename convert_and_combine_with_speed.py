#!/usr/bin/env python3
"""Convert WAV files to MP3 and combine them alphabetically with speed adjustment."""

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

def main(input_folder: str):
    input_folder = convert_windows_to_wsl_path(input_folder)
    input_path = Path(input_folder)
    if not input_path.exists():
        print(f"Error: Folder not found: {input_folder}")
        sys.exit(1)
    
    wav_files = sorted(input_path.glob("*.wav"))
    if not wav_files:
        print(f"No WAV files found in {input_folder}")
        sys.exit(1)
    
    print(f"Found {len(wav_files)} WAV files")
    
    # Step 1: Convert WAV to MP3
    mp3_folder = input_path / "mp3_output"
    mp3_folder.mkdir(exist_ok=True)
    
    mp3_files = []
    for wav_file in wav_files:
        mp3_file = mp3_folder / f"{wav_file.stem}.mp3"
        print(f"Converting: {wav_file.name}")
        subprocess.run(['ffmpeg', '-y', '-i', str(wav_file), str(mp3_file)], 
                      check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mp3_files.append(mp3_file)
    
    print(f"\n✓ Converted {len(mp3_files)} files to MP3")
    
    # Step 2: Combine with speed 1.15
    output_file = input_path / "combined_output.mp3"
    
    print(f"\nAdjusting speed to 1.15x and combining...")
    adjusted_files = []
    for mp3_file in mp3_files:
        adjusted_file = mp3_folder / f"adjusted_{mp3_file.name}"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(mp3_file), 
            "-filter:a", "atempo=1.15", 
            str(adjusted_file)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        adjusted_files.append(adjusted_file)
    
    list_file = mp3_folder / "concat_list.txt"
    with open(list_file, "w") as f:
        for file in adjusted_files:
            f.write(f"file '{file.absolute()}'\n")
    
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", 
                   str(list_file), "-c", "copy", str(output_file)], 
                  check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    list_file.unlink()
    for file in adjusted_files:
        file.unlink()
    
    print(f"\n✓ Combined file created: {output_file}")
    print(f"✓ MP3 files saved in: {mp3_folder}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python convert_and_combine_with_speed.py <input_folder>")
        sys.exit(1)
    
    main(sys.argv[1])
