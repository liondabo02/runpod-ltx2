r"""Sahip geri bildirimi -> kalıcı ders.  Örnek:
python tools\give_feedback.py --worker writer --text "Replikler kısa ve günlük konuşma gibi olsun"
python tools\give_feedback.py --worker writer --retire "günlük konuşma"
python tools\give_feedback.py --list writer
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lessons

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--worker"); p.add_argument("--text"); p.add_argument("--retire"); p.add_argument("--list")
    a = p.parse_args()
    if a.list:
        for r in lessons.top(a.list, 40):
            print(("[SAHİP] " if r["source"] == "owner" else "[oto]   ") + f'({r["count"]}x) ' + r["lesson"])
        return
    if not a.worker:
        p.error("--worker gerekli")
    if a.retire:
        print("Silinen ders sayısı:", lessons.retire(a.worker, a.retire)); return
    if a.text:
        lessons.add(a.worker, a.text, source="owner", count=5)
        print("Ders kaydedildi. Bir sonraki üretimde", a.worker, "işçisi buna uyacak.")

if __name__ == "__main__":
    main()
