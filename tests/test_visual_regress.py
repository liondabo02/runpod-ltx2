"""Önceki görsel hataların regresyon örnekleri (farklı boy/konum/zaman): şapka başta, yaprak gökte, katman sırası."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import props2d, render2d as r2

HEIGHTS = [[1.7, 1.0], [1.0, 1.7], [1.2, 1.2], [1.9, 0.9]]

def test_hat_is_always_on_an_owners_head_not_floating():
    for hs in HEIGHTS:
        for t in (0.0, 1.3, 4.0, 7.9):
            wx, wy = props2d.place("hat", [0.0, 1.0], hs, t, t, 8.0)
            assert min(abs(wy - h * 1.02) for h in hs) < 0.05, (hs, t, wy)       # her zaman bir karakterin baş hizasında
            assert min(abs(wx - 0.0), abs(wx - 1.0)) < 0.3                       # ve onun yanında

def test_leaves_never_drawn_at_face_height():
    for hs in HEIGHTS:
        for t in (0.0, 2.0, 5.0):
            wx, wy = props2d.place("leaves", [0.0, 1.0], hs, t, t, 8.0)
            assert wy >= 1.9 or wy <= 0.15, (hs, t, wy)                          # gökyüzünde ya da yerde; yüz hizasında asla

def test_leaves_are_back_layer_before_characters():
    assert "leaves" in r2.BACK_PROPS                                             # karakterlerden ÖNCE çizilir: yüze binemez
