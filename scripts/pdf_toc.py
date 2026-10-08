#!/usr/bin/env python3
"""
Робить у PDF книги клікабельний зміст і закладки (панель «Зміст» у переглядачі).

Використання:
  python3 scripts/pdf_toc.py book.pdf book-with-toc.pdf

Потрібні: pdftotext (poppler-utils) і pikepdf. Текст і вигляд сторінок не змінюються:
додаються лише невидимі посилання поверх рядків змісту та закладки.
Сторінка для кожного пункту визначається пошуком заголовка в тексті PDF,
а не за номером, надрукованим у змісті.
"""
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, OutlineItem, PageLocation

ENTRY_RX = re.compile(r"^(Розділ\s+\d+|\d+(?:\.\d+)*[А-ЯA-Z]?\.?)\s+(.*)$")
STANDALONE = ["Передмова", "Адміністративно"]  # пункти без номера
LEADER_RX = re.compile(r"[.…·]{4,}|(?:\.\s?){6,}")


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def load_lines(pdf_path: str):
    """[(page_index, x0, y0, x1, y1, text, page_height)] у координатах pdftotext (початок угорі)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "b.html"
        subprocess.run(["pdftotext", "-bbox-layout", pdf_path, str(out)], check=True)
        raw = out.read_text(encoding="utf-8")
    raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw)
    raw = raw.replace("xmlns=", "data-ns=")
    root = ET.fromstring(raw)
    lines = []
    for pi, page in enumerate(root.iter("page")):
        h = float(page.get("height"))
        for ln in page.iter("line"):
            words = [w.text or "" for w in ln.iter("word")]
            text = " ".join(words).strip()
            if not text:
                continue
            lines.append((pi, float(ln.get("xMin")), float(ln.get("yMin")),
                          float(ln.get("xMax")), float(ln.get("yMax")), text, h))
    return lines


def level_of(key: str) -> int:
    if key.startswith("Розділ") or key in STANDALONE:
        return 1
    return min(1 + key.rstrip(".").count("."), 3) if re.match(r"^\d", key) else 1


def main(src: str, dst: str) -> None:
    lines = load_lines(src)

    # початок тіла книги: рядок «Передмова» без крапкових ліній
    body_idx = next(i for i, l in enumerate(lines)
                    if l[5].strip() == "Передмова")
    toc_start = next(i for i, l in enumerate(lines) if l[5].strip() == "ЗМІСТ")
    body_page, body_y = lines[body_idx][0], lines[body_idx][2]
    toc_page = lines[toc_start][0]
    raw_toc = [l for l in lines
               if toc_page <= l[0] <= body_page and (l[0] < body_page or l[2] < body_y - 2)
               and l[5].strip() != "ЗМІСТ"]
    # pdftotext віддає рядки не завжди в порядку читання, а номер сторінки з крапковим
    # заповнювачем іде окремим рядком. Склеюємо рядки з однаковою висотою в один.
    raw_toc.sort(key=lambda l: (l[0], round(l[2] / 3), l[1]))
    toc_lines = []
    for l in raw_toc:
        if toc_lines and toc_lines[-1][0] == l[0] and abs(toc_lines[-1][2] - l[2]) < 4:
            p = toc_lines[-1]
            toc_lines[-1] = (p[0], min(p[1], l[1]), min(p[2], l[2]), max(p[3], l[3]), max(p[4], l[4]),
                             p[5] + " " + l[5], p[6])
        else:
            toc_lines.append(l)
    body_lines = lines[body_idx:]

    # ---- розбір пунктів змісту
    entries = []  # dict(key,title,rects=[(page,x0,y0,x1,y1,h)])
    cur = None
    for (pi, x0, y0, x1, y1, text, h) in toc_lines:
        t = LEADER_RX.sub(" ", text).strip()
        m = ENTRY_RX.match(t)
        stand = next((s for s in STANDALONE if t.startswith(s)), None)
        if stand or (m and (m.group(1).startswith("Розділ") or "." in m.group(1) or re.match(r"^\d+$", m.group(1)))):
            if stand:
                key, title = stand, t
            else:
                key, title = m.group(1).strip(), m.group(2).strip()
            # другий «Розділ 1» тощо не плутаємо: ключ береться з рядка
            cur = {"key": key, "title": title, "rects": [(pi, x0, y0, x1, y1, h)], "page_in_toc": None}
            entries.append(cur)
        elif cur is not None and not t.startswith("Файли") and not t.startswith("Папки"):
            cur["rects"].append((pi, x0, y0, x1, y1, h))
            cur["title"] += " " + t
        # інші рядки (заголовок «Нижче подається…» тощо) ігноруємо

    # Пункти 6.x (опис фотоальбому) не лінкуємо: у тексті їхні назви повторюються
    # у переліку й у самих описах, однозначно визначити сторінку не можна.
    entries = [e for e in entries if not re.match(r"^6\.\d", e["key"])]
    for e in entries:
        t = LEADER_RX.sub(" ", e["title"])
        mp = re.search(r"\s(\d{1,3})\s*$", t.strip())
        e["printed"] = int(mp.group(1)) if mp else None
        t = re.sub(r"\s+\d{1,3}\s*$", "", t.strip())
        t = re.sub(r"[.\s]*(Лещенко|Біла)\b.*$", "", t).strip(" .…")
        t = re.sub(r"^" + re.escape(e["key"].rstrip(".")) + r"\.?\s*", "", t) if re.match(r"^\d", e["key"]) else t
        e["clean"] = t

    # ---- пошук заголовків у тілі, послідовно (порядок книги)
    pos = 0
    found = []
    for e in entries:
        key, tt = e["key"], norm(e["clean"])
        nk = norm(key)
        hit = None
        for j in range(pos, len(body_lines)):
            pi, x0, y0, x1, y1, text, h = body_lines[j]
            if len(text) > 200 or re.search(r"[.…]{4,}", text):
                continue
            if e["printed"] and not (e["printed"] - 4 <= pi + 1 <= e["printed"] + 8):
                continue
            n = norm(text)
            if key in STANDALONE:
                ok = n == norm(key) or (key != "Передмова" and n.startswith(tt[:14]))
            else:
                if not n.startswith(nk):
                    continue
                if re.match(r"^\d", key) and not re.match(r"^\s*" + re.escape(key.rstrip(".")) + r"\.?(\s|$)", text):
                    continue  # напр. елемент списку «55.» не є заголовком 5.5
                rest = n[len(nk):]
                if key.startswith("Розділ"):
                    ok = rest.startswith(tt[:6])
                else:
                    ok = ((not tt and len(rest) > 2) or rest.startswith(tt[:6]) or (len(rest) >= 4 and tt.startswith(rest))
                          or (key[0] in "12345" and len(text) < len(e["clean"]) + 20))
            if ok:
                hit = (j, pi, y0, h)
                break
        e["target"] = hit
        if hit:
            pos = hit[0] + 1
            found.append(e)
        else:
            print(f"НЕ ЗНАЙДЕНО: {key} {e['clean'][:60]} (друк. стор. {e['printed']})")

    for e in found:
        if e["printed"] and abs(e["target"][1] + 1 - e["printed"]) > 1:
            print(f"Сторінка не збігається з друкованою у змісті: {e['key']} {e['clean'][:40]}: у PDF {e['target'][1] + 1}, у змісті {e['printed']}")
    print(f"Пунктів змісту: {len(entries)}, знайдено в тексті: {len(found)}")

    # ---- запис у PDF
    pdf = pikepdf.open(src)
    pages = pdf.pages
    n_links = 0
    for e in found:
        j, tpi, ty, th = e["target"]
        dest = Array([pages[tpi].obj, Name.XYZ, 0, th - ty + 14, None])
        for (pi, x0, y0, x1, y1, h) in e["rects"]:
            rect = [x0 - 2, h - y1 - 2, max(x1, x0 + 40) + 2, h - y0 + 2]
            link = pdf.make_indirect(Dictionary(
                Type=Name.Annot, Subtype=Name.Link, Rect=Array(rect),
                Border=Array([0, 0, 0]), Dest=dest))
            annots = pages[pi].obj.get("/Annots")
            if annots is None:
                pages[pi].obj.Annots = Array([link])
            else:
                annots.append(link)
            n_links += 1

    with pdf.open_outline() as outline:
        outline.root.clear()
        outline.root.append(OutlineItem("Зміст", lines[toc_start][0]))
        stack = []  # (level, item)
        for e in found:
            j, tpi, ty, th = e["target"]
            label = e["clean"] if e["key"] in STANDALONE else f"{e['key'].rstrip('.')} {e['clean']}"
            item = OutlineItem(label[:120], tpi, PageLocation.XYZ, left=0, top=th - ty + 14)
            lvl = level_of(e["key"])
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            if stack:
                stack[-1][1].children.append(item)
            else:
                outline.root.append(item)
            stack.append((lvl, item))

    pdf.Root.PageMode = Name.UseOutlines
    pdf.Root.Lang = pikepdf.String("uk")
    with pdf.open_metadata() as meta:
        meta["dc:title"] = "Село Липляни Житомирської області у спогадах старожилів"
        meta["dc:language"] = ["uk"]
    pdf.docinfo["/Title"] = "Село Липляни Житомирської області у спогадах старожилів"
    pdf.save(dst)
    print(f"Посилань: {n_links}; закладок: {len(found) + 1}; збережено {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
