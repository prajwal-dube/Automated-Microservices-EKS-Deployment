"""Offline demo: SQLITE_PATH and INGEST_TOKEN must be set. Never use for EKS."""
from wsgiref.simple_server import make_server
from .db import Database
from .main import application

if __name__ == "__main__":
    import os
    if not os.getenv("SQLITE_PATH"):
        raise SystemExit("Set SQLITE_PATH for the offline demo")
    Database().migrate()
    with make_server("127.0.0.1", 8000, application) as server:
        print("Offline API listening on http://127.0.0.1:8000", flush=True)
        server.serve_forever()
