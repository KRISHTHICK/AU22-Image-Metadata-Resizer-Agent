# AU22-Image-Metadata-Resizer-Agent
Ai Agent

Image Metadata & Resizer Agent
What it does

Upload one or many images (JPG/PNG/WebP).

Reads and displays EXIF metadata (camera, lens, timestamp, GPS).

Optionally strip sensitive metadata (GPS, serials) before sharing.

Batch resize & compress (by width/height or percentage).

Smart rename using a pattern (e.g., holiday_{index}_{date}).

Download the processed set as a ZIP.

Keeps a short action memory log.

All local: no external APIs.

🔎 How it works (quick)

peek_metadata reads EXIF to preview what’s inside before processing.

process_images:

Loads and orientation-fixes each image.

Resizes based on your mode/value.

Optionally strips GPS and serial-related tags.

Re-embeds EXIF for JPEG when not stripped (best effort).

Renames with pattern tokens and writes to a ZIP in-memory.

Streamlit UI wires it all together and provides a clean download button + report.
