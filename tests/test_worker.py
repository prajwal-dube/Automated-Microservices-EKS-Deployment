import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from probe import config, measure, submit

class Handler(BaseHTTPRequestHandler):
    received = None
    def do_GET(self):
        self.send_response(503 if self.path=="/fail" else 200)
        self.end_headers();self.wfile.write(b"hello")
    def do_POST(self):
        import json
        Handler.received = (self.headers.get("Authorization"), json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(201);self.end_headers();self.wfile.write(b"{}")
    def log_message(self,*_):pass

class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=HTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.thread.join(timeout=3);cls.server.server_close()

    def test_success_and_failure_are_real_statuses(self):
        for path,status in (("/",200),("/fail",503)):
            result=measure({"name":"service","url":self.base+path})
            self.assertEqual(result["status_code"],status)
            self.assertGreaterEqual(result["latency_ms"],0)

    def test_connection_failure_is_recorded(self):
        import socket
        with socket.socket() as unavailable:
            unavailable.bind(("127.0.0.1",0))
            # Bound but not listening: reliably produces a refused connection.
            result=measure({"name":"down","url":f"http://127.0.0.1:{unavailable.getsockname()[1]}"},timeout=0.2)
        self.assertIsNone(result["status_code"])

    def test_submission_includes_auth_and_json(self):
        item={"target":"service","latency_ms":10,"status_code":200}
        submit(self.base,"secret",item)
        self.assertEqual(Handler.received,("Bearer secret",item))

    def test_configuration_rejects_unsafe_or_ambiguous_destinations(self):
        import json
        for targets in ([], [{"name":"ok","url":"file:///etc/passwd"}],
                        [{"name":"ok","url":"http://user:pass@localhost"}],
                        [{"name":"ok","url":self.base},{"name":"ok","url":self.base}],
                        [{"name":"bad name","url":self.base}]):
            with self.subTest(targets=targets), patch.dict(os.environ,{"PROBE_TARGETS":json.dumps(targets),"INGEST_TOKEN":"secret"}):
                with self.assertRaises(ValueError):config()

    def test_valid_configuration(self):
        import json
        with patch.dict(os.environ,{"PROBE_TARGETS":json.dumps([{"name":"ok","url":self.base}]),"INGEST_TOKEN":"secret","PROBE_INTERVAL_SECONDS":"5"}):
            targets,interval=config()
            self.assertEqual(interval,5);self.assertEqual(targets[0]["name"],"ok")
