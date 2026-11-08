"""Shared bounded original-file ingestion."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from fastapi import HTTPException

MAX_FILE = 5 * 1024 * 1024


async def extract_file(file, *, include_links=False, deferred=False):
    raw = await file.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise HTTPException(413, "File exceeds 5 MB")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".txt", ".json", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"):
        raise HTTPException(415, "Use TXT, JSON, PDF, PNG, JPEG, WebP or a single-page TIFF.")
    mime = "text/plain"
    links = []
    extraction = None
    try:
        if deferred and suffix not in ('.txt','.json'):
            mime = {'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
                '.webp':'image/webp','.tif':'image/tiff','.tiff':'image/tiff'}[suffix]
            def validate():
                result=subprocess.run([sys.executable,str(Path(__file__).parent/'read_document.py'),mime,'--validate'],
                    input=raw,capture_output=True,timeout=12)
                if result.returncode:raise ValueError('Invalid image or PDF')
            await asyncio.to_thread(validate)
            text='[Document reading pending. No content has been inferred.]'
            extraction={'version':1,'status':'pending','original_sha256':__import__('hashlib').sha256(raw).hexdigest()}
        elif suffix == ".pdf":
            def parse():
                result = subprocess.run([sys.executable, str(Path(__file__).parent / "parse_pdf.py")], input=raw, capture_output=True, timeout=12)
                if result.returncode != 0:
                    raise ValueError("PDF extraction failed")
                return json.loads(result.stdout)
            parsed = await asyncio.to_thread(parse)
            text = parsed['text']
            links = parsed.get('links', [])
            mime = "application/pdf"
        elif suffix in ('.txt','.json'):
            text = raw.decode("utf-8-sig")
            mime = "application/json" if suffix == ".json" else "text/plain"
            if suffix == ".json": json.loads(text)
        else:
            raise ValueError('Image reading requires durable ingestion')
        if "\x00" in text or len(text) > 30000 or not text.strip():
            raise ValueError("Empty, binary, or over 30,000 extracted characters")
    except Exception:
        raise HTTPException(422, "Could not safely parse this file. Use UTF-8 text, an unencrypted PDF of at most 30 pages, or a supported image of at most 12 million pixels.") from None
    if deferred:return raw,text,mime,links,extraction
    return (raw, text, mime, links) if include_links else (raw, text, mime)
