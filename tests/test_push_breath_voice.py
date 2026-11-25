import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import push_breath_voice  # noqa: E402

TOKEN = "test-admin-token"


class FakeMindFit(BaseHTTPRequestHandler):
    """The admin API and the storage PUT on one port; records every request."""

    calls = []
    fail = {}  # "METHOD path" -> status to answer instead

    def log_message(self, *args):
        pass

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _reply(self, status, payload=None):
        data = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self):
        body = self._body()
        key = f"{self.command} {self.path}"
        FakeMindFit.calls.append({"key": key, "auth": self.headers.get("Authorization"),
                                  "type": self.headers.get("Content-Type"), "body": body})
        if key in FakeMindFit.fail:
            return self._reply(FakeMindFit.fail[key], {"code": "2900", "message": "nope"})
        if key == "POST /api/v1/admin/media/uploads":
            n = sum(c["key"] == key for c in FakeMindFit.calls)
            asset = f"asset-{n}"
            port = self.server.server_address[1]
            return self._reply(201, {"asset": {"id": asset}, "upload_url": f"http://127.0.0.1:{port}/storage/{asset}",
                                     "upload_headers": {"Content-Type": "audio/mp4"}})
        if self.command == "PUT" and self.path.startswith("/storage/"):
            return self._reply(200)
        if self.command == "POST" and self.path.endswith("/confirm"):
            return self._reply(200, {"id": self.path.split("/")[-2], "state": "READY"})
        if self.command == "PUT" and self.path.startswith("/api/v1/admin/content/breath-voice/"):
            cue = self.path.rsplit("/", 1)[1]
            sent = json.loads(body)
            return self._reply(200, {"cue": cue, "audio": {"id": sent["audio_asset_id"]}})
        return self._reply(404, {"code": "404"})

    do_GET = do_POST = do_PUT = _handle


def make_clip(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=440:r=24000:d={seconds}",
                    "-c:a", "aac", "-b:a", "128k", str(path)], check=True)


class PushBreathVoiceTests(unittest.TestCase):
    def setUp(self):
        FakeMindFit.calls, FakeMindFit.fail = [], {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMindFit)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.api = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "clips").mkdir()
        self.json = self.dir / "breath_voice.json"
        self.json.write_text(json.dumps({"voice": "Rina", "cues": ["intro", "finish"],
                                         "parts": [{"style": "s", "text": "a"}, {"style": "s", "text": "b"}]}))
        make_clip(self.dir / "clips" / "intro.m4a", 1.5)
        make_clip(self.dir / "clips" / "finish.m4a", 0.8)

    def tearDown(self):
        self.server.shutdown()

    def keys(self):
        return [c["key"] for c in FakeMindFit.calls]

    def test_each_cue_is_uploaded_confirmed_and_assigned(self):
        assigned = push_breath_voice.push(self.json, self.api, TOKEN)
        self.assertEqual(assigned, [("intro", "asset-1"), ("finish", "asset-2")])
        self.assertEqual(self.keys(), [
            "POST /api/v1/admin/media/uploads", "PUT /storage/asset-1", "POST /api/v1/admin/media/asset-1/confirm",
            "PUT /api/v1/admin/content/breath-voice/intro",
            "POST /api/v1/admin/media/uploads", "PUT /storage/asset-2", "POST /api/v1/admin/media/asset-2/confirm",
            "PUT /api/v1/admin/content/breath-voice/finish"])
        prepare = json.loads(FakeMindFit.calls[0]["body"])
        self.assertEqual(prepare["kind"], "AUDIO")
        self.assertEqual(prepare["mime_type"], "audio/mp4")
        self.assertEqual(prepare["file_name"], "intro.m4a")
        self.assertEqual(prepare["size"], (self.dir / "clips" / "intro.m4a").stat().st_size)
        self.assertEqual(FakeMindFit.calls[1]["body"], (self.dir / "clips" / "intro.m4a").read_bytes())
        self.assertAlmostEqual(json.loads(FakeMindFit.calls[2]["body"])["duration_ms"], 1500, delta=80)
        self.assertEqual(json.loads(FakeMindFit.calls[3]["body"]), {"audio_asset_id": "asset-1"})

    def test_the_admin_calls_carry_the_token_and_storage_does_not(self):
        push_breath_voice.push(self.json, self.api, TOKEN)
        for call in FakeMindFit.calls:
            expected = None if call["key"].startswith("PUT /storage/") else f"Bearer {TOKEN}"
            self.assertEqual(call["auth"], expected, call["key"])
        self.assertEqual(FakeMindFit.calls[1]["type"], "audio/mp4")

    def test_a_missing_clip_stops_before_any_upload(self):
        (self.dir / "clips" / "finish.m4a").unlink()
        with self.assertRaises(SystemExit) as stop:
            push_breath_voice.push(self.json, self.api, TOKEN)
        self.assertIn("finish.m4a", str(stop.exception))
        self.assertEqual(FakeMindFit.calls, [])

    def test_a_refused_call_stops_and_names_it(self):
        FakeMindFit.fail["PUT /api/v1/admin/content/breath-voice/intro"] = 403
        with self.assertRaises(SystemExit) as stop:
            push_breath_voice.push(self.json, self.api, TOKEN)
        self.assertIn("PUT /content/breath-voice/intro -> 403", str(stop.exception))
        self.assertNotIn("POST /api/v1/admin/media/uploads", self.keys()[4:])

    def test_no_token_stops(self):
        with self.assertRaises(SystemExit) as stop:
            push_breath_voice.push(self.json, self.api, "")
        self.assertIn("MINDFIT_ADMIN_TOKEN", str(stop.exception))
        self.assertEqual(FakeMindFit.calls, [])


if __name__ == "__main__":
    unittest.main()
