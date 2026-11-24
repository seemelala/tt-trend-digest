"""send() against a local HTTP server that stands in for the chat services."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from helpers import at, default_config_path, fixture_fetch

from trend_digest import build_digest, send

ANSWERS = {
    "/discord": (204, ""),
    "/slack": (500, "server error"),
    "/wecom": (200, '{"errcode":0,"errmsg":"ok"}'),
    "/dingtalk-refused": (200, '{"errcode":310000,"errmsg":"keywords not in content"}'),
    "/feishu": (200, '{"code":0,"msg":"success"}'),
}


class Handler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Handler.received.append((self.path, json.loads(body)))
        path = self.path.split("?")[0]
        if path.endswith("/sendMessage"):
            status, text = 200, '{"ok":true,"result":{}}'
        else:
            status, text = ANSWERS.get(path, (404, "no such hook"))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, *args):
        pass


class SendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.digest = build_digest(default_config_path(), fetch=fixture_fetch(), now=at("2026-11-24"))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.received.clear()

    def targets(self):
        return {"discord": f"{self.base}/discord", "slack": f"{self.base}/slack",
                "wecom": f"{self.base}/wecom", "feishu": {"url": f"{self.base}/feishu", "secret": "s3"},
                "dingtalk": {"url": f"{self.base}/dingtalk-refused", "secret": "abc"},
                "telegram": {"token": "123:abc", "chat_id": "-100", "api_base": self.base}}

    def test_one_failure_does_not_stop_the_others(self):
        results = {r["channel"]: r for r in send(self.digest, self.targets())}
        self.assertTrue(results["discord"]["ok"])
        self.assertEqual(results["discord"]["status"], 204)
        self.assertFalse(results["slack"]["ok"])
        self.assertEqual(results["slack"]["status"], 500)
        self.assertTrue(results["wecom"]["ok"])
        self.assertTrue(results["telegram"]["ok"])
        self.assertTrue(results["feishu"]["ok"])
        self.assertFalse(results["dingtalk"]["ok"], "HTTP 200 with errcode is a failure")
        self.assertIn("310000", results["dingtalk"]["error"])

    def test_request_details(self):
        send(self.digest, self.targets())
        paths = [p for p, _ in Handler.received]
        self.assertIn("/discord?with_components=true", paths)
        self.assertTrue(any(p.startswith("/dingtalk-refused?timestamp=") and "&sign=" in p for p in paths))
        telegram = next(b for p, b in Handler.received if p.endswith("/sendMessage"))
        self.assertEqual(telegram["chat_id"], "-100")
        feishu = next(b for p, b in Handler.received if p == "/feishu")
        self.assertIn("sign", feishu)
        self.assertEqual(feishu["msg_type"], "interactive")

    def test_errors_do_not_show_the_webhook_path(self):
        results = {r["channel"]: r for r in send(self.digest, self.targets())}
        self.assertNotIn("/slack", results["slack"]["error"])
        self.assertIn("127.0.0.1", results["slack"]["error"])

    def test_dry_run_sends_nothing(self):
        results = send(self.digest, self.targets(), dry_run=True)
        self.assertEqual(Handler.received, [])
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r["ok"] for r in results))

    def test_only_given_channels_are_sent(self):
        results = send(self.digest, {"discord": f"{self.base}/discord"})
        self.assertEqual([r["channel"] for r in results], ["discord"])


if __name__ == "__main__":
    unittest.main()
