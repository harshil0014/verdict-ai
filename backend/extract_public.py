"""Offline bounded text extraction subprocess. Never fetches embedded URLs."""
import json
import re
import sys
from io import BytesIO
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(10,10))
    resource.setrlimit(resource.RLIMIT_AS,(384*1024*1024,384*1024*1024))
except ImportError: pass
raw=sys.stdin.buffer.read(5*1024*1024+1)
if len(raw)>5*1024*1024: raise ValueError('size')
mime=sys.argv[1];metadata={};title='';text=''
if mime=='application/pdf':
    from pypdf import PdfReader
    doc=PdfReader(BytesIO(raw))
    if doc.is_encrypted or len(doc.pages)>30: raise ValueError('PDF bounds')
    text='\n\n'.join('[Page '+str(i+1)+']\n'+(page.extract_text() or '') for i,page in enumerate(doc.pages))
    title=str((doc.metadata or {}).get('/Title',''))[:200]
    metadata['extractor']='pypdf'
elif mime in ('text/html','application/xhtml+xml'):
    import trafilatura
    from lxml import html
    tree=html.fromstring(raw)
    titles=tree.xpath('//title/text()');title=' '.join(titles).strip()[:200]
    # Dates are accepted only from explicit publication metadata; Last-Modified
    # and guessed dates are never promoted to a publication date.
    dates=tree.xpath('//meta[@property="article:published_time"]/@content | //meta[@name="citation_publication_date"]/@content | //meta[@name="DC.date.issued"]/@content')
    for value in dates:
        if re.match(r'^\d{4}-\d{2}-\d{2}(?:T|$)',value):
            from datetime import date
            date.fromisoformat(value[:10]);metadata.update(publication_date=value[:10],publication_date_basis='explicit HTML publication metadata; source-stated, not independently authenticated');break
    text=trafilatura.extract(raw,include_comments=False,include_tables=True,include_links=False,output_format='txt',favor_recall=True) or ''
    metadata['extractor']='trafilatura'
else:
    text=raw.decode('utf-8-sig')
    if mime=='application/json': json.loads(text)
    metadata['extractor']='utf8'
if '\x00' in text: raise ValueError('binary')
text=text.strip();truncated=len(text)>30000;text=text[:30000]
issued=re.search(r'Date Issued:\s*([A-Z][a-z]+ \d{1,2}, \d{4})',text[:1000])
indexed=re.search(r'Indexed as:\s*([^\n]{5,150})',text[:1000])
if indexed: title=indexed[1].strip()
if issued:
    from datetime import datetime
    metadata.update(publication_date=datetime.strptime(issued[1],'%B %d, %Y').date().isoformat(),publication_date_basis='Explicit Date Issued in preserved document; source-stated date')
print(json.dumps({'text':text,'title':title,'metadata':metadata,'truncated':truncated},ensure_ascii=True))
