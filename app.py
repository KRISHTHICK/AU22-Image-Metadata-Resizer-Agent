import streamlit as st
import pandas as pd

from image_tools import process_images, peek_metadata

st.set_page_config(page_title="Image Metadata & Resizer Agent", page_icon="🖼️", layout="wide")
st.title("🖼️ Image Metadata & Resizer Agent")

# Memory (short log)
if "memory" not in st.session_state:
    st.session_state.memory = []

def log(msg: str):
    st.session_state.memory.append(msg)
    st.session_state.memory = st.session_state.memory[-50:]

# ---- Upload ----
st.sidebar.header("1) Upload Images")
files = st.sidebar.file_uploader(
    "Choose images (JPG/PNG/WebP)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True
)

if files:
    # Show quick metadata peek
    rows = peek_metadata([(f.read(), f.name) for f in files])
    st.subheader("📋 Metadata Preview")
    st.dataframe(pd.DataFrame(rows))

# ---- Settings ----
st.sidebar.header("2) Processing Settings")

resize_mode = st.sidebar.selectbox("Resize by", ["Percent", "Width", "Height"], index=0)
resize_value = st.sidebar.number_input(
    "Resize value",
    min_value=1,
    max_value=10000,
    value=50 if resize_mode == "Percent" else 1200,
    step=1,
)

output_format = st.sidebar.selectbox("Output format", ["jpg", "png", "webp"], index=0)
quality = st.sidebar.slider("Quality (JPEG/WEBP)", min_value=1, max_value=100, value=85)

st.sidebar.header("Privacy")
strip_gps = st.sidebar.checkbox("Strip GPS data", value=True)
strip_serials = st.sidebar.checkbox("Strip serials/owner tags", value=True)

st.sidebar.header("Renaming")
rename_pattern = st.sidebar.text_input(
    "Pattern (tokens: {index}, {name}, {date})",
    value="img_{index}_{date}"
)

# ---- Run ----
st.sidebar.header("3) Run")
run = st.sidebar.button("Process Images")

if run:
    if not files:
        st.warning("Please upload at least one image.")
    else:
        st.info("Processing images…")
        # Re-read bytes because Streamlit's file object is consumed
        file_pairs = [(f.getvalue(), f.name) for f in files]
        zip_bytes, report = process_images(
            file_pairs,
            resize_mode=resize_mode,
            resize_value=int(resize_value),
            output_format=output_format,
            quality=int(quality),
            strip_gps=strip_gps,
            strip_serials=strip_serials,
            rename_pattern=rename_pattern,
        )
        log(f"Processed {len(file_pairs)} images → {len(report)} outputs, format={output_format}.")
        st.success("Done! Download your ZIP below and review the report.")

        # Download
        st.download_button(
            label="⬇️ Download Processed Images (ZIP)",
            data=zip_bytes,
            file_name="processed_images.zip",
            mime="application/zip",
        )

        # Report table
        st.subheader("📑 Processing Report")
        st.dataframe(pd.DataFrame(report))

# ---- Memory ----
st.divider()
st.subheader("🧾 Action Memory")
if st.session_state.memory:
    for m in st.session_state.memory:
        st.write(m)
else:
    st.caption("(empty)")
