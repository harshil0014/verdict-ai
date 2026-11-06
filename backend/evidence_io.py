"""Shared bounded original-file ingestion."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from fastapi import HTTPException

MAX_FILE = 5 * 1024 * 1024


async def extract_file(file):
    raw = await file.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise HTTPException(413, "File exceeds 5 MB")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".txt", ".json", ".pdf"):
        raise HTTPException(415, "Use TXT, JSON, or a text-bearing PDF. Images and executable files are not accepted.")
    mime = "text/plain"
    try:
        if suffix == ".pdf":
            def parse():
                result = subprocess.run([sys.executable, str(Path(__file__).parent / "parse_pdf.py")], input=raw, capture_output=True, timeout=12)
                if result.returncode != 0:
                    raise ValueError("PDF extraction failed")
                return json.loads(result.stdout)["text"]
            text = await asyncio.to_thread(parse)
            mime = "application/pdf"
        else:
            text = raw.decode("utf-8-sig")
            mime = "application/json" if suffix == ".json" else "text/plain"
            if suffix == ".json": json.loads(text)
        if "\x00" in text or len(text) > 30000 or not text.strip():
            raise ValueError("Empty, binary, or over 30,000 extracted characters")
    except Exception:
        raise HTTPException(422, "Could not safely parse this file. Use UTF-8 text or an unencrypted text-bearing PDF of at most 30 pages and 30,000 characters.") from None
    return raw, text, mime
