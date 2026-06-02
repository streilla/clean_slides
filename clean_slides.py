import os
import tifftools
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--input_dir', type=str, required=True)
args = parser.parse_args()

# File to track processed slides
PROCESSED_LOG = Path(f"{args.input_dir}/.processed_slides.log")

def sanitize_slide(path: Path):
    tmp_path = path.with_suffix(".tmp.svs")

    try:
        info = tifftools.read_tiff(str(path))

        for ifd in info["ifds"]:
            tag_id = tifftools.Tag.ImageDescription.value
            if tag_id in ifd["tags"]:
                raw = ifd["tags"][tag_id]["data"]
                if isinstance(raw, str):
                    clean = raw.replace("\x00", "").strip()
                else:
                    clean = raw.decode("latin-1", errors="replace").replace("\x00", "").strip()
                ifd["tags"][tag_id]["data"] = clean

        # Write to a temp file alongside the original
        tifftools.write_tiff(info, str(tmp_path))

        # Atomic replace — if the VM dies before this, original is intact
        os.replace(tmp_path, path)

        # Log the processed file
        with open(PROCESSED_LOG, "a") as f:
            f.write(f"{path}\n")

        print(f"  Done: {path.name}")

    except Exception as e:
        print(f"  Error: {path.name}: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        raise

def sanitize_directory(directory: str, extensions=(".tif", ".tiff", ".svs", ".ndpi")):
    root = Path(directory)
    slides = [p for p in root.rglob("*") if p.suffix.lower() in extensions]

    # Skip already-processed and in-progress files
    slides = [p for p in slides if not p.name.endswith(".tmp.svs")]

    # Load the list of already processed slides
    processed = set()
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r") as f:
            processed = {Path(line.strip()) for line in f if line.strip()}

    # Filter out already processed slides
    slides = [p for p in slides if p not in processed]

    print(f"Found {len(slides)} slides to process (already processed: {len(processed)})")

    for i, slide_path in enumerate(slides):
        print(f"[{i+1}/{len(slides)}] {slide_path.name}")

        # Remove leftover .tmp.svs files
        tmp_path = slide_path.with_suffix(".tmp.svs")
        if tmp_path.exists():
            print(f"  Found leftover .tmp.svs, resuming slide sanitizing...")
            tmp_path.unlink()

        sanitize_slide(slide_path)
        
    if PROCESSED_LOG.exists():
        PROCESSED_LOG.unlink()
        
    print("All done.")

sanitize_directory(args.input_dir)