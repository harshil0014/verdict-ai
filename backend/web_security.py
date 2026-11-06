"""Same-origin and response-header boundary."""
import os
from fastapi.responses import JSONResponse


class BoundedBodyMiddleware:
    """Bound streamed/chunked uploads before JSON or multipart parsing allocates."""
    def __init__(self, app, limit=5*1024*1024+100000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] in ('GET', 'HEAD', 'OPTIONS'):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > self.limit:
                return await JSONResponse({'detail':'Request is too large'},413,
                    headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})(scope,receive,send)
            chunks.append(chunk)
            if not message.get('more_body',False): break
        first = True
        async def replay():
            nonlocal first
            if first:
                first = False
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)


async def guard(request, call_next):
    host = request.headers.get("host", "")
    configured = os.getenv("VERDICT_PUBLIC_HOST", "")
    allowed = {"127.0.0.1:8000", "localhost:8000", "testserver"}
    if configured: allowed.add(configured)
    if host not in allowed: return JSONResponse({"detail": "Host is not allowed"}, 400)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{host}", f"https://{host}", "http://127.0.0.1:5173", "http://localhost:5173"}:
            return JSONResponse({"detail": "Cross-origin request refused"}, 403)
        size = request.headers.get("content-length")
        if size and (not size.isdigit() or int(size) > 5*1024*1024+100000):
            return JSONResponse({"detail": "Request is too large"}, 413)
    result = await call_next(request)
    result.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
        "Cache-Control": "private, no-store" if request.url.path.startswith("/api") else "no-cache",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
    return result
