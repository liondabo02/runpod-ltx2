import http.client, json, os, sys, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import office_server as osv
import engine_gaps

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(REPO, "studio", "office", "index_canli.html")


def test_motor_paneli_haritadan_ve_formullerden_gelir():
    d = osv.engine_panel(REPO, max_age=0)
    rep = engine_gaps.check(REPO)
    assert d["toplam"] == rep["toplam"] and d["yetenek_sayisi"] == rep["yetenek_sayisi"]
    assert {f["format"] for f in d["formuller"]} >= {"gizem_komedi_ekibi", "sessiz_kovalamaca", "koy_toplulugu"}
    for f in d["formuller"]:
        assert sum(f["sayim"].values()) == f["gerekli"]
        assert all(" " in e for e in f["eksik"])  # kod + sade ad (sahip kodları ezberlemek zorunda değil)
    assert "profesyonel kalite değildir" in d["not"]


def test_motor_paneli_onbellegi_ve_kabul_kaydi(tmp_path):
    # geçici kökte: harita + formül yok -> yine de çökmez; kabul kaydı en yeni önce
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "studio"))
    with open(os.path.join(root, "studio", "engine_capabilities.json"), "w", encoding="utf-8") as f:
        json.dump({"yetenekler": [{"id": "X-1", "motor": "m", "isci": "w", "skill": "s", "yetenek": "x", "kanit": [], "test": []}]}, f)
    os.makedirs(os.path.join(root, "runtime", "software-dept"))
    with open(os.path.join(root, "runtime", "software-dept", "kabul.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"at": 1, "sonuc": "RED", "head": "aaaaaaa1"}) + "\n" + "bozuk satır\n" +
                json.dumps({"at": 2, "sonuc": "KABUL", "head": "bbbbbbb2"}) + "\n")
    d = osv.engine_panel(root, max_age=0)
    assert d["toplam"]["YOK"] == 1 and d["formuller"] == []
    assert [k["sonuc"] for k in d["kabul"]] == ["KABUL", "RED"] and d["kabul"][0]["head"] == "bbbbbbb"


def test_ofis_ekrani_motor_panelini_ve_eski_hata_ayrimini_icerir():
    s = open(HTML, encoding="utf-8").read()
    assert "/api/motorlar" in s and 'id="motor"' in s and 'id="formul"' in s
    assert "hatalı (son 24 saat)" in s and "eski hata kaydı" in s
    assert "function hataSay(js,now){return js.filter(j=>j.state==='failed'&&(j.at==null||now-j.at<86400)).length}" in s


def test_gercek_sunucu_motor_api(monkeypatch):
    calls = []
    monkeypatch.setattr(osv, "engine_panel", lambda: calls.append(1) or {"toplam": {"VAR": 1}})
    srv = osv.ThreadingHTTPServer(("127.0.0.1", 0), osv.H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/api/motorlar", headers={"Host": "127.0.0.1:%d" % port})
        r = c.getresponse()
        assert r.status == 200 and json.loads(r.read())["toplam"] == {"VAR": 1} and calls
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/api/motorlar", headers={"Host": "kotu.example"})
        assert c.getresponse().status == 403  # yabancı Host yine reddedilir
    finally:
        srv.shutdown(); srv.server_close()


def test_isler_zaman_damgasi_tasir(tmp_path, monkeypatch):
    q = tmp_path / "q"; q.mkdir()
    (q / "a.failed.json").write_text(json.dumps({"command": "x", "error": "e"}), encoding="utf-8")
    old = time.time() - 3 * 86400
    os.utime(q / "a.failed.json", (old, old))
    monkeypatch.setattr(osv, "Q", str(q))
    js = osv.jobs()
    assert js[0]["state"] == "failed" and abs(js[0]["at"] - old) < 2
