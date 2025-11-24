# gunicorn_trending.py - Config for Trending Server (Port 8100)
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8100')}"
backlog = 2048

workers = int(os.getenv('GUNICORN_WORKERS', min(4, (multiprocessing.cpu_count() * 2) + 1)))
worker_class = 'sync'
worker_connections = 1000
timeout = 60
keepalive = 5
graceful_timeout = 30

max_requests = 1000
max_requests_jitter = 50

accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True

preload_app = False

def on_starting(server):
    print("="*80)
    print("🚀 TRENDING SERVER STARTING")
    print(f"   Workers: {workers}")
    print(f"   Timeout: {timeout}s")
    print(f"   Port: {os.getenv('PORT', '8100')}")
    print("="*80)

def when_ready(server):
    print("✅ Trending server ready")

def worker_int(worker):
    print(f"⚠️  Worker {worker.pid} shutting down gracefully")

def post_worker_init(worker):
    print(f"👷 Worker {worker.pid} initialized")