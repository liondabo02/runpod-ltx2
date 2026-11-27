import json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import office_live as ol, worker_events as we, studio_daemon as sdm

W = [("showrunner", "CEO", "r", True), ("voice", "Ses", "r", True), ("fx_layer", "Efekt", "r", True)]


def ev(worker, kind, at, job="j1", text="t"):
    return {"worker": worker, "kind": kind, "at": at, "job": job, "text": text}


def st(live, i):
    return next(w for w in live if w["id"] == i)


class Derive(unittest.TestCase):
    def test_no_events_means_nobody_works(self):
        self.assertEqual({w["state"] for w in ol.derive(W, [], ["j1"], True, 10)}, {"idle"})

    def test_working_needs_alive_studio_and_running_job(self):
        e = [ev("voice", "start", 1)]
        self.assertEqual(st(ol.derive(W, e, ["j1"], True, 10), "voice")["state"], "working")
        for running, alive in ((["j1"], False), ([], True), (["baska"], True)):   # bilerek bozulmuş durumlar
            self.assertEqual(st(ol.derive(W, e, running, alive, 10), "voice")["state"], "interrupted")

    def test_done_failed_and_duration(self):
        s = st(ol.derive(W, [ev("voice", "start", 1), ev("voice", "failed", 3.5, text="ses yok")], ["j1"], True, 10), "voice")
        self.assertEqual((s["state"], s["last"]["ok"], s["last"]["seconds"]), ("idle", False, 2.5))

    def test_queue_done_with_failed_worker_is_not_success(self):
        e = [ev("showrunner", "start", 1), ev("voice", "start", 2), ev("voice", "failed", 3), ev("showrunner", "done", 4)]
        live = ol.derive(W, e, [], True, 5)
        self.assertFalse(st(live, "showrunner")["last"]["ok"])
        self.assertIn("BAŞARILI DEĞİL", ol.facts(live, [], True))

    def test_note_without_start_or_from_other_job_does_not_activate(self):
        self.assertEqual(st(ol.derive(W, [ev("voice", "note", 1)], ["j1"], True, 10), "voice")["state"], "idle")
        s = st(ol.derive(W, [ev("voice", "start", 1, text="a"), ev("voice", "note", 2, job="eski", text="b")], ["j1"], True, 10), "voice")
        self.assertEqual(s["text"], "a")


class Events(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.p = os.path.join(self.d.name, "e.jsonl")

    def tearDown(self):
        self.d.cleanup()

    def test_without_job_id_nothing_is_written(self):
        with mock.patch.dict(os.environ, {"AHOS_EVENTS_PATH": self.p}, clear=False):
            os.environ.pop("AHOS_JOB_ID", None)
            with we.working("voice", "x") as a:
                a.done("y")
        self.assertFalse(os.path.exists(self.p))

    def test_working_closes_on_exception_and_missing_result(self):
        with mock.patch.dict(os.environ, {"AHOS_EVENTS_PATH": self.p, "AHOS_JOB_ID": "j1"}):
            with self.assertRaises(ValueError):
                with we.working("voice", "x"):
                    we.note("adım"); raise ValueError("bozuk")
            with we.working("render", "x"):
                pass
            open(self.p, "a").write('{"yarım')
            rows = we.read()
        self.assertEqual([(r["worker"], r["kind"]) for r in rows],
                         [("voice", "start"), ("voice", "note"), ("voice", "failed"), ("render", "start"), ("render", "failed")])

    def test_daemon_reports_manager_result(self):
        q = os.path.join(self.d.name, "q"); os.makedirs(q)
        with mock.patch.dict(os.environ, {"AHOS_EVENTS_PATH": self.p}), mock.patch.object(sdm, "Q", q):
            for name, runner, want in (("a", lambda j: {}, "done"), ("b", lambda j: 1 / 0, "failed")):
                json.dump({"command": "x"}, open(os.path.join(q, name + ".pending.json"), "w"))
                sdm.run_job(name + ".pending.json", runner=runner)
                self.assertEqual([r["kind"] for r in we.read() if r["job"] == name], ["start", want])


class Ceo(unittest.TestCase):
    def test_classify(self):
        for msg, want in [("Park kuralları hakkında yeni bölüm hazırla", "task"), ("durum ne?", "status"), ("Kim çalışıyor?", "status"),
                          ("bitti mi", "status"), ("işi durdur", "stop"), ("İptal et", "stop"), ("merhaba nasılsın", "chat"),
                          ("film yapabilir misin?", "chat"), ("bu bölüm nasıl olacak?", "chat"),
                          ("Aden parkta top oynasın bölüm olsun", "task")]:
            self.assertEqual(ol.classify(msg), want, msg)

    def test_task_only_proposes(self):
        with mock.patch("studio_enqueue.enqueue") as enq:
            r = ol.ceo_reply("yeni bölüm hazırla", ol.derive(W, [], [], False, 0), [], False, model=lambda *a: self.fail("model"))
        self.assertEqual(r["proposal"], {"action": "enqueue", "command": "yeni bölüm hazırla"}); enq.assert_not_called()

    def test_status_comes_from_records_not_model(self):
        live = ol.derive(W, [ev("voice", "start", 1, text="3. repliği okuyor")], ["j1"], True, 2)
        r = ol.ceo_reply("durum ne", live, [{"id": "j1", "state": "running"}], True, model=lambda *a: self.fail("model"))
        self.assertEqual(r["source"], "kayit"); self.assertIn("3. repliği okuyor", r["reply"])
        off = ol.ceo_reply("durum ne", ol.derive(W, [ev("voice", "start", 1)], [], False, 2), [], False)
        self.assertIn("Stüdyo kapalı", off["reply"]); self.assertNotIn("Ses çalışıyor", off["reply"])

    def test_stop_without_job_and_model_down(self):
        self.assertIsNone(ol.ceo_reply("durdur", [], [], True)["proposal"])
        r = ol.ceo_reply("merhaba", ol.derive(W, [], [], True, 0), [], True, model=lambda *a: None)
        self.assertEqual(r["source"], "kural"); self.assertIn("ulaşamıyorum", r["reply"])
        def dead(*a, **k): raise OSError("kapalı")
        self.assertIsNone(ol.model_reply("x", "y", env={}, opener=dead))


if __name__ == "__main__":
    unittest.main()
