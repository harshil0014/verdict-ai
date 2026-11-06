"""Single-document snapshots, not a crawler. No cookies, auth, proxy or scripts."""
import asyncio
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit
import httpx

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 30000


class RetrievalError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def normalize_url(value):
    if len(value)>2048 or any(ord(c)<33 or ord(c)==127 for c in value) or '\\' in value:
        raise RetrievalError('unsafe_url','Use a complete public HTTP(S) URL without spaces or control characters.')
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not p.hostname or p.username is not None or p.password is not None:
            raise ValueError()
        host=p.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        if p.port not in (None,443 if p.scheme=='https' else 80): raise ValueError()
        if host=='localhost' or host.endswith(('.localhost','.local','.internal','.home','.test','.invalid')) or '.' not in host and ':' not in host:
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global: raise ValueError()
        except ValueError as e:
            if re.fullmatch(r'[0-9.:]+',host) or ':' in host: raise e
        # URLs carrying credentials are not public evidence links.
        from urllib.parse import parse_qsl
        if any(re.search(r'(^|[_-])(token|key|password|secret|signature|credential|auth|session|access)([_-]|$)',k,re.I) for k,v in parse_qsl(p.query)):
            raise ValueError()
        netloc='['+host+']' if ':' in host else host
        return urlunsplit((p.scheme,netloc,p.path or '/',p.query,''))
    except (ValueError,UnicodeError):
        raise RetrievalError('unsafe_url','Only public HTTP(S) pages on standard ports are allowed. Private addresses, credentials and signed links are refused.') from None


async def public_addresses(url):
    p=urlsplit(normalize_url(url))
    try:
        rows=await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(p.hostname,443 if p.scheme=='https' else 80,type=socket.SOCK_STREAM,flags=socket.AI_ADDRCONFIG),10)
    except (OSError,TimeoutError):
        raise RetrievalError('dns_failed','The public hostname could not be resolved.') from None
    addresses=list(dict.fromkeys(row[4][0] for row in rows))
    if not addresses or any(isinstance(ipaddress.ip_address(ip),ipaddress.IPv6Address) and ipaddress.ip_address(ip).ipv4_mapped is not None and not ipaddress.ip_address(ip).ipv4_mapped.is_global for ip in addresses):
        raise RetrievalError('unsafe_url','The hostname resolves to a private or non-public address.')
    if any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise RetrievalError('unsafe_url','The hostname resolves to a private or non-public address.')
    return addresses


async def fetch_bytes(url):
    requested=normalize_url(url); current=requested; redirects=[]
    async with asyncio.timeout(40):
        for _ in range(4):
            addresses=await public_addresses(current)
            p=urlsplit(current);ip=addresses[0]
            target=urlunsplit((p.scheme,'['+ip+']' if ':' in ip else ip,p.path,p.query,''))
            # Connect to the validated address; keep original hostname for TLS
            # SNI/certificate checks and HTTP Host. DNS is never re-resolved by
            # the transport, closing the DNS-rebinding gap.
            try:
                async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
                    async with client.stream('GET',target,headers={'Host':p.netloc,'Accept':'text/html,application/pdf,text/plain,application/json','Accept-Encoding':'identity','User-Agent':'VERDICT-PublicEvidence/1.0 (single URL; no crawling)'},extensions={'sni_hostname':p.hostname}) as r:
                        if r.status_code in (301,302,303,307,308):
                            location=r.headers.get('location','')
                            if not location: raise RetrievalError('invalid_redirect','The page returned an unusable redirect.')
                            next_url=normalize_url(urljoin(current,location))
                            if p.scheme=='https' and urlsplit(next_url).scheme!='https': raise RetrievalError('unsafe_url','HTTPS-to-HTTP redirects are refused.')
                            redirects.append({'from':current,'to':next_url,'status':r.status_code});current=next_url;continue
                        if r.status_code!=200:
                            raise RetrievalError('http_'+str(r.status_code),'The source returned HTTP '+str(r.status_code)+'. No document was invented. Try an official alternative or upload a copy you are authorized to provide.')
                        mime=r.headers.get('content-type','').split(';')[0].lower()
                        if mime not in ('text/html','application/xhtml+xml','application/pdf','text/plain','application/json'):
                            raise RetrievalError('unsupported_type','Use a public HTML, PDF, text or JSON document.')
                        length=r.headers.get('content-length','')
                        if length.isdigit() and int(length)>MAX_BYTES: raise RetrievalError('too_large','Public snapshots are limited to 5 MB.')
                        chunks=[];size=0
                        async for chunk in r.aiter_bytes():
                            size+=len(chunk)
                            if size>MAX_BYTES: raise RetrievalError('too_large','The decoded source exceeds 5 MB.')
                            chunks.append(chunk)
                        return b''.join(chunks),{'requested_url':requested,'final_url':current,'redirects':redirects,'mime':mime,'retrieved_at':datetime.now(timezone.utc).isoformat(),'last_modified_header':r.headers.get('last-modified'),'etag':r.headers.get('etag'),'retrieval_method':'direct_http_snapshot','publication_date':None,'publication_date_basis':None,'historical_applicability':'not_established'}
            except httpx.HTTPError:
                raise RetrievalError('network_failed','The source could not be retrieved over a verified public connection. Try later or upload an authorized copy.') from None
        raise RetrievalError('redirect_limit','The source exceeded three redirects; no page was accepted.')


async def retrieve(url):
    try: raw,meta=await fetch_bytes(url)
    except TimeoutError: raise RetrievalError('timeout','Retrieval exceeded 40 seconds. Try an official alternative or upload an authorized copy.') from None
    def extract():
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('extract_public.py')),meta['mime']],input=raw,capture_output=True,timeout=15)
        if result.returncode: raise RetrievalError('unreadable','The page could not be safely extracted. It may require JavaScript, authentication or an unencrypted text PDF. No browser challenge was bypassed.')
        return json.loads(result.stdout)
    try: extracted=await asyncio.to_thread(extract)
    except subprocess.TimeoutExpired: raise RetrievalError('extraction_timeout','Document extraction timed out; use an authorized text copy.') from None
    meta.update(extracted['metadata'])
    text=extracted['text']
    if len(text.strip())<80: raise RetrievalError('no_content','No substantive source text was retrieved. Search snippets and model recollections are not evidence.')
    if re.search(r'^(access denied|just a moment|verify you are human|enable javascript)',text.strip(),re.I):
        raise RetrievalError('access_blocked','The site returned an access challenge; use an authorized copy or another official source.')
    meta.update(raw_sha256=hashlib.sha256(raw).hexdigest(),text_sha256=hashlib.sha256(text.encode()).hexdigest(),byte_count=len(raw),text_characters=len(text),excerpt_truncated=extracted['truncated'])
    archive=re.fullmatch(r'/web/(\d{14})(?:id_)?/(https?://.*)',urlsplit(meta['final_url']).path)
    if urlsplit(meta['final_url']).hostname=='web.archive.org' and archive:
        meta.update(archive_capture_requested=archive[1],archived_original_url=archive[2],historical_applicability='archive_capture_does_not_prove_policy_effective_dates')
    return {'raw':raw,'text':text,'metadata':meta,'title':extracted['title'] or urlsplit(meta['final_url']).hostname}
