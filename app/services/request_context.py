"""Request metadata only; never retain tokens, bodies, IPs or secret URLs."""
from contextvars import ContextVar

request_context = ContextVar("request_context", default={})
language_context = ContextVar("language_context", default="ar")
