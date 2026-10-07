import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.db import Database
from app.main import Application
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from probe import measure, submit

class QuietHandler(WSGIRequestHandler):
    def log_message(self, *_):
        pass

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"SQLITE_PATH": str(Path(self.folder.name)/"test.db"), "INGEST_TOKEN": "test-token"})
        self.env.start()
        self.db = Database()
        self.db.migrate()
        self.app = Application(self.db)

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    def call(self, path, method="GET", payload=None, token=None, raw=None, content_type="application/json"):
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else b"")
        endpoint, _, query = path.partition("?")
        env = {"REQUEST_METHOD":method,"PATH_INFO":endpoint,"QUERY_STRING":query,
               "CONTENT_TYPE":content_type,"CONTENT_LENGTH":str(len(body)),"wsgi.input":io.BytesIO(body)}
        if token is not None:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        captured = []
        response = b"".join(self.app(env, lambda status, headers: captured.append((status, headers))))
        return int(captured[0][0].split()[0]), json.loads(response)

    def observation(self, **overrides):
        return {"target":"api", "latency_ms":12.3,"status_code":200, **overrides}

    def insert(self, **overrides):
        return self.call("/api/observations", "POST", self.observation(**overrides), "test-token")

    def test_health_and_empty_database(self):
        self.assertEqual(self.call("/healthz")[0], 200)
        self.assertEqual(self.call("/readyz")[0], 200)
        self.assertEqual(self.call("/api/targets")[1], {"targets":[]})

    def test_ingestion_requires_token(self):
        for token in (None, "wrong", "tést"):
            self.assertEqual(self.call("/api/observations", "POST", self.observation(), token)[0], 401)

    def test_roundtrip_latest_and_history(self):
        self.assertEqual(self.insert()[0], 201)
        self.assertEqual(self.insert(latency_ms=8, status_code=503)[0], 201)
        targets = self.call("/api/targets")[1]["targets"]
        self.assertEqual(len(targets), 1)
        self.assertFalse(targets[0]["healthy"])
        self.assertEqual(targets[0]["status_code"], 503)
        self.assertIn("+00:00", targets[0]["observed_at"])
        history = self.call("/api/history?target=api&limit=1")[1]["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["latency_ms"], 8)

    def test_target_isolation_and_order(self):
        self.insert(target="zulu")
        self.insert(target="alpha")
        targets = self.call("/api/targets")[1]["targets"]
        self.assertEqual([t["target"] for t in targets], ["alpha","zulu"])
        self.assertEqual(len(self.call("/api/history?target=alpha")[1]["history"]), 1)

    def test_invalid_values_are_rejected(self):
        for values in ({"latency_ms":float("nan")},{"latency_ms":float("inf")},{"latency_ms":True},
                       {"latency_ms":-1},{"status_code":999},{"status_code":True},
                       {"target":"bad';DROP TABLE observations;--"},{"target":""},{"target":"x"*65}):
            with self.subTest(values=values):
                self.assertEqual(self.insert(**values)[0], 400)
        self.assertEqual(self.call("/readyz")[0], 200)

    def test_unhealthy_timeout_and_redirect_status(self):
        self.assertFalse(self.insert(status_code=None)[1]["healthy"])
        self.assertTrue(self.insert(status_code=302)[1]["healthy"])

    def test_bad_body_and_content_type(self):
        self.assertEqual(self.call("/api/observations", "POST", token="test-token", raw=b"{")[0], 400)
        self.assertEqual(self.call("/api/observations", "POST", token="test-token", raw=b"[]")[0], 400)
        self.assertEqual(self.call("/api/observations", "POST", token="test-token", raw=b"x"*4097)[0], 413)
        self.assertEqual(self.call("/api/observations", "POST", self.observation(), "test-token", content_type="text/plain")[0], 415)

    def test_invalid_history_limit(self):
        for query in ("", "target=api&limit=0", "target=api&limit=201", "target=api&limit=x", "target=bad%27"):
            self.assertEqual(self.call("/api/history?"+query)[0], 400)

    def test_retention_expires_old_observations(self):
        self.insert()
        with self.db.connect() as conn:
            conn.execute("UPDATE observations SET observed_at=1")
        self.insert(target="fresh")
        self.assertEqual(self.call("/api/history?target=api")[1]["history"], [])

    def test_db_outage_does_not_break_liveness(self):
        with patch.object(self.db, "ready", side_effect=RuntimeError("db unavailable")):
            self.assertEqual(self.call("/readyz")[0], 503)
            self.assertEqual(self.call("/healthz")[0], 200)

    def test_methods_and_unknown_routes(self):
        self.assertEqual(self.call("/api/targets", "DELETE")[0], 405)
        self.assertEqual(self.call("/missing")[0], 404)

    def test_actual_http_request_roundtrip(self):
        with make_server("127.0.0.1", 0, self.app, handler_class=QuietHandler) as server:
            thread=threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base=f"http://127.0.0.1:{server.server_port}"
                request=Request(base+"/api/observations",data=json.dumps(self.observation()).encode(),
                                headers={"Content-Type":"application/json","Authorization":"Bearer test-token"})
                with urlopen(request,timeout=3) as response:
                    self.assertEqual(response.status,201)
                probe=measure({"name":"http-integration","url":base+"/readyz"})
                submit(base,"test-token",probe)
                with urlopen(base+"/api/history?target=http-integration",timeout=3) as response:
                    saved=json.load(response)["history"][0]
                    self.assertEqual(saved["status_code"],200)
                    self.assertEqual(saved["latency_ms"],probe["latency_ms"])
                with urlopen(base+"/api/targets",timeout=3) as response:
                    self.assertEqual(json.load(response)["targets"][0]["target"],"api")
            finally:
                server.shutdown();thread.join(timeout=3)
