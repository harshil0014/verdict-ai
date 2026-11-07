"""Extract text in a disposable process; never render active content."""

import sys, io, json

try:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    except ImportError:
        pass
    from pypdf import PdfReader

    raw = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024 or not raw.startswith(b"%PDF-"):
        raise ValueError()
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 30:
        raise ValueError()
    pages = []
    links = []
    size = 0
    for i, p in enumerate(reader.pages):
        content = p.extract_text() or ""
        size += len(content)
        if size > 30000:
            raise ValueError()
        pages.append(f"[Page {i + 1}]\n" + content)
        for annotation in p.get('/Annots', []):
            row = annotation.get_object()
            action = row.get('/A')
            if action:
                action = action.get_object()
                uri = str(action.get('/URI', ''))
                if action.get('/S') == '/URI' and uri.startswith(('https://', 'http://')) and len(uri) <= 2048 and len(links) < 20:
                    links.append({'url': uri, 'page': i + 1})
    if size < 20:
        raise ValueError()
    sys.stdout.write(json.dumps({"text": "\n\n".join(pages), "links": links}))
except Exception:
    sys.exit(2)
