import time, uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EMAIL = "24f2007319@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://app-ai0giw.example.com"
EXAM_ORIGIN = "https://exam.sanand.workers.dev"  # see step 2
LIMIT, WINDOW = 15, 10  # 15 requests per 10 seconds

app = FastAPI()
hits = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":  # don't count preflights
            return await call_next(request)
        client = request.headers.get("x-client-id", "anonymous")
        now = time.monotonic()
        q = hits[client]
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= LIMIT:
            return JSONResponse({"detail": "Too Many Requests"}, status_code=429)
        q.append(now)
        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


# Order matters: the last one added is the OUTERMOST.
app.add_middleware(RateLimitMiddleware)       # innermost
app.add_middleware(RequestContextMiddleware)  # so 429s also get X-Request-ID
app.add_middleware(                           # outermost: CORS headers on everything, incl. 429
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN, EXAM_ORIGIN],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"],          # browser can't read the header without this
)


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}