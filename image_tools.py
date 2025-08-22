import io
import os
import re
import zipfile
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from PIL import Image, ImageOps
import piexif

# ---------- Helpers ----------

def _read_exif_bytes(pil_image: Image.Image) -> Dict:
    try:
        exif_bytes = pil_image.info.get("exif", None)
        if not exif_bytes:
            return {}
        exif_dict = piexif.load(exif_bytes)
        return exif_dict
    except Exception:
        # Some images may have malformed EXIF; ignore safely
        return {}

def _format_exif_for_display(exif_dict: Dict) -> Dict[str, str]:
    if not exif_dict:
        return {}

    out = {}
    # Primary tags we care about
    zeroth = exif_dict.get("0th", {})
    exif   = exif_dict.get("Exif", {})
    gps    = exif_dict.get("GPS", {})

    def get_tag(d, tag):
        return d.get(tag, None)

    # Common tags
    model = get_tag(zeroth, piexif.ImageIFD.Model)
    make = get_tag(zeroth, piexif.ImageIFD.Make)
    software = get_tag(zeroth, piexif.ImageIFD.Software)
    dt = get_tag(zeroth, piexif.ImageIFD.DateTime) or get_tag(exif, piexif.ExifIFD.DateTimeOriginal)

    if model: out["Camera Model"] = model.decode("utf-8", "ignore") if isinstance(model, bytes) else str(model)
    if make: out["Camera Make"] = make.decode("utf-8", "ignore") if isinstance(make, bytes) else str(make)
    if software: out["Software"] = software.decode("utf-8", "ignore") if isinstance(software, bytes) else str(software)
    if dt: out["DateTime"] = dt.decode("utf-8", "ignore") if isinstance(dt, bytes) else str(dt)

    # Lens info sometimes in Exif
    lensmodel = exif.get(piexif.ExifIFD.LensModel)
    if lensmodel:
        out["Lens"] = lensmodel.decode("utf-8", "ignore") if isinstance(lensmodel, bytes) else str(lensmodel)

    # GPS
    if gps:
        out["GPS Present"] = "Yes"
    else:
        out["GPS Present"] = "No"

    return out

def _strip_sensitive_exif(exif_dict: Dict, strip_gps: bool, strip_serials: bool) -> Dict:
    if not exif_dict:
        return {}

    exif_copy = {k: dict(v) if isinstance(v, dict) else v for k, v in exif_dict.items()}

    if strip_gps and "GPS" in exif_copy:
        exif_copy["GPS"] = {}

    if strip_serials:
        # Remove known serial-related tags if present
        for sect, tag in [
            ("Exif", piexif.ExifIFD.BodySerialNumber),
            ("Exif", piexif.ExifIFD.LensSerialNumber),
            ("0th", piexif.ImageIFD.CameraOwnerName),
        ]:
            if sect in exif_copy and tag in exif_copy[sect]:
                exif_copy[sect].pop(tag, None)

    return exif_copy

def _resize_image(img: Image.Image, mode: str, value: int) -> Image.Image:
    if mode == "Width":
        w = value
        ratio = w / img.width
        h = max(1, int(img.height * ratio))
        return img.resize((w, h), Image.LANCZOS)
    elif mode == "Height":
        h = value
        ratio = h / img.height
        w = max(1, int(img.width * ratio))
        return img.resize((w, h), Image.LANCZOS)
    elif mode == "Percent":
        pct = max(1, value)
        w = max(1, int(img.width * pct / 100))
        h = max(1, int(img.height * pct / 100))
        return img.resize((w, h), Image.LANCZOS)
    else:
        return img

def _normalize_format(ext: str) -> Tuple[str, str]:
    ext = ext.lower().strip(".")
    if ext in ("jpg", "jpeg"):
        return ("JPEG", "jpg")
    if ext == "png":
        return ("PNG", "png")
    if ext == "webp":
        return ("WEBP", "webp")
    # default to jpg
    return ("JPEG", "jpg")

def _build_filename(pattern: str, index: int, orig_name: str, dt: Optional[str]) -> str:
    """
    pattern supports tokens: {index}, {name}, {date} (YYYYMMDD)
    """
    base = os.path.splitext(os.path.basename(orig_name))[0]
    date_token = ""
    if dt:
        # dt like '2023:09:10 14:23:11' -> 20230910
        try:
            if ":" in dt and " " in dt:
                date_token = datetime.strptime(dt, "%Y:%m:%d %H:%M:%S").strftime("%Y%m%d")
            else:
                date_token = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
        except Exception:
            date_token = ""
    out = pattern.format(index=index, name=re.sub(r"\\W+", "_", base), date=date_token)
    return out

# ---------- Core Batch Processor ----------

def process_images(
    files: List[Tuple[bytes, str]],
    resize_mode: str = "Percent",   # "Width" | "Height" | "Percent"
    resize_value: int = 50,
    output_format: str = "jpg",     # jpg | png | webp
    quality: int = 85,              # for JPEG/WEBP
    strip_gps: bool = True,
    strip_serials: bool = True,
    rename_pattern: str = "img_{index}_{date}",
) -> Tuple[bytes, List[Dict]]:
    """
    Returns: (zip_bytes, report_rows)
    report_rows: [{"original":..., "new_name":..., "size":..., "exif_removed":True/False}]
    """
    report = []
    mem_zip = io.BytesIO()
    out_ext_fmt, out_ext = _normalize_format(output_format)

    with zipfile.ZipFile(mem_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, (bts, fname) in enumerate(files, start=1):
            with Image.open(io.BytesIO(bts)) as img:
                img = ImageOps.exif_transpose(img)  # fix orientation
                exif_dict = _read_exif_bytes(img)
                display_exif = _format_exif_for_display(exif_dict)
                dt = display_exif.get("DateTime")

                # Resize
                resized = _resize_image(img, resize_mode, resize_value)

                # Prepare EXIF (might be stripped)
                out_exif_dict = _strip_sensitive_exif(exif_dict, strip_gps, strip_serials)
                exif_bytes = None
                if out_exif_dict:
                    try:
                        exif_bytes = piexif.dump(out_exif_dict)
                    except Exception:
                        exif_bytes = None  # if malformed, continue without EXIF

                # Rename
                new_base = _build_filename(rename_pattern, idx, fname, dt)
                new_name = f"{new_base}.{out_ext}"

                # Save into zip
                save_kwargs = {}
                if out_ext_fmt in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = int(quality)
                    if out_ext_fmt == "JPEG":
                        save_kwargs["optimize"] = True
                        save_kwargs["progressive"] = True

                out_buf = io.BytesIO()
                if exif_bytes and out_ext_fmt == "JPEG":
                    resized.save(out_buf, format=out_ext_fmt, exif=exif_bytes, **save_kwargs)
                else:
                    resized.save(out_buf, format=out_ext_fmt, **save_kwargs)
                out_buf.seek(0)

                zf.writestr(new_name, out_buf.read())

                report.append({
                    "original": fname,
                    "new_name": new_name,
                    "width": resized.width,
                    "height": resized.height,
                    "format": out_ext_fmt,
                    "exif_removed": bool(exif_dict and not _read_exif_bytes(resized)),  # best-effort flag
                    "gps_present_before": display_exif.get("GPS Present", "No"),
                })

    mem_zip.seek(0)
    return mem_zip.read(), report

def peek_metadata(files: List[Tuple[bytes, str]]) -> List[Dict]:
    """
    Fast EXIF peek for UI before processing.
    """
    rows = []
    for bts, fname in files:
        try:
            with Image.open(io.BytesIO(bts)) as img:
                img = ImageOps.exif_transpose(img)
                exif_dict = _read_exif_bytes(img)
                disp = _format_exif_for_display(exif_dict)
                rows.append({
                    "file": fname,
                    "width": img.width,
                    "height": img.height,
                    "camera": disp.get("Camera Make", "") + " " + disp.get("Camera Model", ""),
                    "date": disp.get("DateTime", ""),
                    "gps": disp.get("GPS Present", "No"),
                })
        except Exception as e:
            rows.append({"file": fname, "error": str(e)})
    return rows
