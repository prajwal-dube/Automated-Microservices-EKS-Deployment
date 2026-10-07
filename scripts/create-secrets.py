#!/usr/bin/env python3
"""Send credentials via stdin; never store them in Helm release values or argv."""
import argparse
import base64
import getpass
import json
import os
import secrets
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--compose", action="store_true")
args = parser.parse_args()
if args.compose:
    path = Path(__file__).resolve().parents[1] / ".env"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(f"DB_PASSWORD={secrets.token_urlsafe(32)}\nINGEST_TOKEN={secrets.token_urlsafe(32)}\n")
    print("Created .env with random local credentials; existing files are never overwritten.")
else:
    password = getpass.getpass("Database password (retain it; reuse on future installs): ")
    if len(password) < 16:
        raise SystemExit("Use a database password of at least 16 characters")
    namespace = {"apiVersion":"v1","kind":"Namespace","metadata":{"name":"netops"}}
    subprocess.run(["kubectl","apply","-f","-"], input=json.dumps(namespace), text=True, check=True)
    secret = {"apiVersion":"v1","kind":"Secret","metadata":{"name":"netops-secrets","namespace":"netops"},
              "type":"Opaque", "data": {key:base64.b64encode(value.encode()).decode() for key,value in
              {"DB_PASSWORD":password,"INGEST_TOKEN":secrets.token_urlsafe(32)}.items()}}
    # create, not apply: accidental rotations must fail, since existing DB password persists.
    subprocess.run(["kubectl","create","-f","-"], input=json.dumps(secret), text=True, check=True)
    print("Created netops-secrets. If rotating the ingest token, restart api and worker.")
