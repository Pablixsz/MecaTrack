"""Rate limiting (OWASP API4/API2). The limits are per client IP and come from config.py."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
