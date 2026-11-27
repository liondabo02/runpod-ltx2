import http.client, json, os, sys, tempfile, threading, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import office_server as osv, render_worker as rw, render_episode as re_


class Allowed(unittest.TestCase):
    def test_own_page_and_local_tools(self):
        for host, origin in [("127.0.0.1:8787", None), ("localhost:8787", "http://localhost:8787"),
                             ("127.0.0.1:8787", "http://127.0.0.1:8787"), ("[::1]:8787", "http://[::1]:8787")]:
            self.assertTrue(osv.request_allowed(host, origin, 8787), (host, origin))

    def test_foreign_and_lookalike_rejected(self):
        for host, origin in [("127.0.0.1:8787", "http://localhost.kotu.example"), ("127.0.0.1:8787", "http://kotu.example/?127.0.0.1"),
                             ("127.0.0.1:8787", "http://127.0.0.1.kotu.example:8787"), ("127.0.0.1:8787", "null"),
                             ("127.0.0.1:8787", "http://localhost:3000"), ("127.0.0.1:8787", "https://localhost:8787"),
                             ("kotu.example:8787", None), ("", None), ("127.0.0.1:abc", None)]:
            self.assertFalse(osv.request_allowed(host, origin, 8787), (host, origin))

    def test_real_server_rejects_before_any_side_effect(self):
        srv = osv.ThreadingHTTPServer(("127.0.0.1", 0), osv.H); port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def post(origin):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                c.request("POST", "/api/command", json.dumps({"command": "x", "autostart": False}), {"Origin": origin, "Content-Type": "text/plain"})
                return c.getresponse().status
            with mock.patch.object(osv.studio_enqueue, "enqueue", return_value="j") as enq:
                self.assertEqual(post("http://localhost.kotu.example"), 403); enq.assert_not_called()
                self.assertEqual(post("http://127.0.0.1:%d" % port), 200); enq.assert_called_once()
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", "/api/live", headers={"Host": "kotu.example"})
            self.assertEqual(c.getresponse().status, 403)
        finally:
            srv.shutdown(); srv.server_close()


class ExitCodes(unittest.TestCase):
    def test_render_worker_only_passed_is_zero(self):
        self.assertEqual(rw.exit_code({"status": "PASSED"}), 0)
        for m in ({"status": "BLOCKED"}, {"status": "FAILED"}, {}, None):
            self.assertNotEqual(rw.exit_code(m), 0, m)

    def test_render_episode_failed_video_qa_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            sdir = os.path.join(d, "series", "s"); os.makedirs(os.path.join(sdir, "episodes", "e001"))
            json.dump({}, open(os.path.join(sdir, "series-bible.json"), "w"))
            with mock.patch.object(re_, "ROOT", d), mock.patch.object(re_.rw, "run", return_value={"status": "PASSED", "clip": "c"}), \
                 mock.patch.object(re_.vqa, "check", return_value={"verdict": "FAIL", "problems": ["donuk kare"]}), \
                 mock.patch.object(sys, "argv", ["x", "--series-id", "s", "--episode", "e001"]):
                with self.assertRaises(SystemExit) as cm:
                    re_.main()
            self.assertEqual(cm.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
