"""
Gunicorn settings (loaded automatically from the working directory).

One worker with threads on purpose: the rate limiter (memory://) and the JWT
logout blocklist live in process memory, so several worker processes would
each keep their own copy (a revoked token would still work on another worker).
Threads share that memory and fit in the 512 MB of a free PaaS instance.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get('WEB_CONCURRENCY', 1))
threads = int(os.environ.get('GUNICORN_THREADS', 4))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 60))
graceful_timeout = 20
accesslog = '-'
errorlog = '-'
wsgi_app = 'app:create_app()'
