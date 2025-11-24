# gunicorn_config.py - Universal configuration for all services
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', min(4, (multiprocessing.cpu_count() * 2) + 1)))
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers periodically
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# CRITICAL: Set to False for background threads to work
preload_app = False

def on_starting(server):
    """Called before master process starts"""
    print("="*80)
    print("🚀 GUNICORN STARTING")
    print(f"   Workers: {workers}")
    print(f"   Port: {os.getenv('PORT', '8000')}")
    print(f"   Preload: {preload_app} (MUST BE FALSE)")
    print("="*80)

def when_ready(server):
    """Called when server is ready"""
    print("✅ Server ready - workers will initialize on first request")

def worker_int(worker):
    """Called when worker receives SIGINT/SIGTERM"""
    print(f"⚠️  Worker {worker.pid} shutting down")