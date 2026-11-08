"""Offline, disposable document reader. No URLs, document scripts or network.

The parent bounds wall time. Linux also bounds memory/CPU; only one page and
one Tesseract process are live at a time. Coordinates describe the normalized
page image, never the physical delivery location.
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import warnings

MAX_PIXELS = 12_000_000
MAX_PAGES = 10


def image(raw):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    warnings.simplefilter('error', Image.DecompressionBombWarning)
    im = Image.open(io.BytesIO(raw))
    if im.format not in ('PNG', 'JPEG', 'WEBP', 'TIFF') or getattr(im, 'n_frames', 1) != 1:
        raise ValueError('Unsupported or multi-frame image')
    if im.width * im.height > MAX_PIXELS:
        raise ValueError('Image exceeds 12 million pixels')
    im.load()
    im = ImageOps.exif_transpose(im).convert('RGBA')
    clean = Image.new('RGB', im.size, 'white')
    clean.paste(im, mask=im.getchannel('A'))
    clean.thumbnail((2400, 3200))
    return clean


def ocr(im):
    binary = os.getenv('TESSERACT_CMD') or shutil.which('tesseract')
    if not binary:
        raise RuntimeError('OCR engine unavailable')
    with tempfile.TemporaryDirectory(prefix='verdict-ocr-') as folder:
        filename = str(Path(folder) / 'page.png')
        im.save(filename)
        env = {**os.environ, 'OMP_THREAD_LIMIT': '1'}
        run = subprocess.run([binary, filename, 'stdout', '-l', 'eng', '--psm', '3', 'tsv'],
            capture_output=True, timeout=22, env=env)
        if run.returncode:
            raise RuntimeError('OCR engine could not read page')
    lines = {}
    words = []
    for r in csv.DictReader(io.StringIO(run.stdout.decode('utf8')), delimiter='\t'):
        if r.get('level') != '5' or not r.get('text', '').strip():
            continue
        confidence = float(r['conf'])
        text = r['text'] if confidence >= 55 else '[unclear]'
        key = (r['block_num'], r['par_num'], r['line_num'])
        lines.setdefault(key, []).append(text)
        words.append({'text': text, 'confidence': round(confidence, 2),
            'box': [int(r[k]) for k in ('left', 'top', 'width', 'height')]})
        if len(words) > 4000:
            raise ValueError('Too many words')
    text = '\n'.join(' '.join(v) for v in lines.values())
    readable = [w for w in words if w['text'] != '[unclear]']
    return {'text': text if readable else '[Unreadable page: no reliable printed text extracted]',
        'words': words, 'width': im.width, 'height': im.height,
        'status': 'uncertain' if len(readable) < 4 or len(readable) != len(words) else 'extracted',
        'method': 'tesseract', 'confidence_note': 'Engine scores are heuristics, not calibrated probabilities or authentication.'}


def read(raw, mime, *, validate=False, vision=False):
    pages = []
    links = []
    if mime == 'application/pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 30:
            raise ValueError('Use an unencrypted PDF of at most 30 pages')
        if validate:
            return {'valid': True}
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(raw) as doc:
            scanned = 0
            for n, page in enumerate(reader.pages):
                for ref in (page.get('/Annots') or [])[:100]:
                    try:
                        action=ref.get_object().get('/A') or {}
                        url=str(action.get('/URI',''))
                        if action.get('/S')=='/URI' and url.startswith(('https://','http://')) and len(url)<=2048 and len(links)<20:
                            links.append({'url':url,'page':n+1})
                    except Exception:pass
                text = (page.extract_text() or '').strip()
                if len(text) >= 40:
                    pages.append({'page': n + 1, 'method': 'pdf_text', 'text': text, 'status': 'extracted'})
                else:
                    scanned += 1
                    if scanned > MAX_PAGES:
                        pages.append({'page': n + 1, 'method': 'not_read', 'text': '[Page not read: ten scanned-page limit]', 'status': 'unreadable'})
                        continue
                    rendered=doc[n]
                    try:
                        w, h = rendered.get_size()
                        scale = min(2.5, (MAX_PIXELS / max(1, w * h)) ** .5, 2400 / max(w, h))
                        bitmap = rendered.render(scale=scale)
                        try:
                            im = bitmap.to_pil().convert('RGB')
                        finally:
                            bitmap.close()
                    finally:
                        rendered.close()
                    row = ocr(im)
                    row['page'] = n + 1
                    if vision:
                        out = io.BytesIO(); im.save(out, format='JPEG', quality=85)
                        row['vision_image'] = base64.b64encode(out.getvalue()).decode()
                    pages.append(row)
                if sum(len(p['text']) for p in pages) > 29000:
                    raise ValueError('Extracted document exceeds 30,000 characters')
    else:
        im = image(raw)
        if validate:
            return {'valid': True}
        row = ocr(im)
        row['page'] = 1
        if vision:
            out = io.BytesIO(); im.save(out, format='JPEG', quality=85)
            row['vision_image'] = base64.b64encode(out.getvalue()).decode()
        pages.append(row)
    text = '\n\n'.join('[Page %s]\n%s' % (p['page'], p['text']) for p in pages)
    if len(text) > 30000:
        raise ValueError('Extracted document exceeds 30,000 characters')
    return {'text': text, 'pages': pages, 'links':links, 'status': 'uncertain' if any(p['status'] != 'extracted' for p in pages) else 'extracted',
        'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
        'warning': 'Machine transcription may contain errors. Inspect the original; extraction does not authenticate the document.'}


if __name__ == '__main__':
    try:
        if sys.platform != 'win32':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (380 * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
        raw = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError('File exceeds limit')
        print(json.dumps(read(raw, sys.argv[1], validate='--validate' in sys.argv, vision='--vision' in sys.argv)))
    except Exception:
        sys.exit(2)
