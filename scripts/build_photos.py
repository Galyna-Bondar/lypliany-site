#!/usr/bin/env python3
"""
Готує фото для сайту: стискає у WebP (два розміри), прибирає EXIF/GPS, прибирає точні дублікати,
записує src/data/photos.json і docs/photos-todo.md.

Використання (з кореня репозиторію):
  python3 scripts/build_photos.py "<папка ФОТОАЛЬБОМ>" "<Вибране з фотоальбому>.docx"

Підписи беруться лише з двох місць: з підписів автора у docx «Вибране з фотоальбому» і з назв
файлів, які дав автор. Підписів не вигадуємо: де їх нема, поле caption = null.
Оригінали копіюються в originals/photos/ (ця папка не потрапляє в git) для завантаження в R2.
"""
import hashlib
import json
import time
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps

W_THUMB, W_VIEW = 480, 1200
QUALITY = 78
IMG_EXT = {".jpg", ".jpeg", ".png"}
WORK_DIR = "6.5. Липляни, Чоповичі"  # робоча папка автора: дублікати 6.5.x + 35 фото «Чоповичі, 100 років»
SECTION_CHOPOVYCHI = "Чоповичі (з папки автора «100 років»)"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Теми: slug, довідковий номер розділу книги, назва (як у змісті книги)
THEMES = [
    ("karty", "6.1", "Карти України й плани села"),
    ("tserkva-budivli", "6.2", "Церква, будівлі, в'яз-ясен"),
    ("ferma", "6.3", "Залишки будівель зруйнованої ферми, 90-ті роки"),
    ("pobut", "6.4", "Предмети побуту"),
    ("sviata", "6.5", "Святкові дні"),
    ("bobyk", "6.6", "Бобик М. Д."),
    ("rizne", "6.7", "Різні цікавинки"),
    ("tsentr-2017", "6.8", "Центр села 2017 року"),
    ("tsentr-onovlenyi", "6.9", "Центр села, оновлений громадою 2017 р., та подорож селом"),
    ("shkola", "6.10", "Шкільні роки"),
    ("okremi", "6.12–6.21", "Окремі світлини з архіву"),
    ("ekskursiia", "6.11В", "Екскурсія селом (кадри з відеокліпу)"),
]
TITLE = {t[0]: t[2] for t in THEMES}

# Папки альбому -> тема
FOLDER_THEME = [
    ("6.1-", "karty"), ("6.2-", "tserkva-budivli"), ("6.3-", "ferma"), ("6.4-", "pobut"),
    ("6.5-", "sviata"), ("6.6-", "bobyk"), ("6.7-", "rizne"), ("6.8-", "tsentr-2017"),
    ("6.9-", "tsentr-onovlenyi"), ("6.10-", "shkola"),
]
# Файли в корені альбому за початком назви -> тема
ROOT_THEME = {"6.14": "shkola", "6.15": "shkola"}
# Підрозділи 6.5 (назви з книги)
SECTIONS_65 = {
    "6.5.1": "Сарафина Бехова (Шмагун Сарафина)",
    "6.5.2": "Марія і Степан Філонишин (Кондрачук Степан)",
    "6.5.3": "Вишивка Раї Шикарного",
    "6.5.4": "Дубас Ольга",
    "6.5.5": "Дубас Ольга, 1906 року народження, ювілей — 100 років",
    "6.5.6": "Пам'ять: після урочистої частини біля меморіалу",
}

CAMERA_ID = re.compile(
    r"^(?:DSC_?\d+|IMG_?\d+(?:\(\d+\))?|P\d{7}|\d{8}_\d{6}|село\s+Липляни\s+\d+|img\d+|olymp\d*)(?![\w])", re.I)
LEAD_REF = re.compile(r"^6\.\d+[А-Яа-я]?[\s.\-–]*")
LEAD_INDEX = re.compile(r"^\d{1,2}(?:[\s\-–]+)(?=\D)")


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ahash(im: Image.Image) -> int:
    g = im.convert("L").resize((8, 8), Image.LANCZOS)
    px = list(g.tobytes())
    avg = sum(px) / 64
    return sum(1 << i for i, v in enumerate(px) if v > avg)


# Очевидні друкарські помилки в підписах (автор набирав їх у назвах файлів)
CAPTION_FIXES = {
    "Хата Тимоха,Федори": "Хата Тимоха, Федори",
    "Початк20, за цією хатою": "Початок 20 ст., за цією хатою",
    "початк 20ст, за цією хатою": "початок 20 ст., за цією хатою",
    "Сім_я": "Сім'я",
    "почакку 20 стоіття": "початку 20 століття",
    "бусел , в": "бусел, в",
    "Коресподента": "Кореспондента",
    "мам'ятник": "пам'ятник",
    "ссолома": "солома",
    "ліворруч": "ліворуч",
    "Маомацьких": "Макомацьких",
    "таких велике поле": "таке велике поле",
    "св’яткуванні": "святкуванні",
    "1958рік": "1958 рік",
    "на Чумаки Фото": "на Чумаки. Фото",
    "на Чумаки та центр села Фото": "на Чумаки та центр села. Фото"
}


def fix_caption(c):
    if not c:
        return c
    for a, b in CAPTION_FIXES.items():
        c = c.replace(a, b)
    return c


def caption_from_name(name: str):
    c = Path(name).stem
    for _ in range(4):
        before = c
        c = LEAD_REF.sub("", c).strip(" -–._")
        c = CAMERA_ID.sub("", c).strip(" -–._")
        c = LEAD_INDEX.sub("", c).strip(" -–._")
        c = re.sub(r"\(\d+\)$", "", c).strip(" -–._")
        if c == before:
            break
    c = re.sub(r"\s+[–-]\s*копія$", "", c)
    c = re.sub(r"\s+", " ", c)
    if re.search(r"\s\d{3,}$", c) or re.match(r"^[PpРр]\d{5,}", c):
        return None  # службові номери камери, а не підпис
    if not c or re.fullmatch(r"[\d\W_]+", c) or CAMERA_ID.fullmatch(c) or re.fullmatch(r"[A-Za-z]*\d+", c):
        return None
    return c[0].upper() + c[1:]


def natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def docx_images(docx: Path, outdir: Path):
    """[(photo_no|None, caption|None, extracted_path)] у порядку документа."""
    z = zipfile.ZipFile(docx)
    rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    rid2target = {r.get("Id"): r.get("Target") for r in rels}
    doc = ET.fromstring(z.read("word/document.xml"))
    outdir.mkdir(parents=True, exist_ok=True)
    items = []
    pending = []
    cap_rx = re.compile(r"^\s*(\d+)\s*[-–.]+\s*(.+)$", re.S)
    for p in doc.iter("{%s}p" % NS["w"]):
        blips = [b.get("{%s}embed" % NS["r"]) for b in p.iter("{%s}blip" % NS["a"])]
        for rid in blips:
            target = rid2target.get(rid)
            if target:
                pending.append(target)
        text = "".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])).strip()
        if text:
            m = cap_rx.match(text)
            if m and pending:
                no, cap = int(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip(" -–")
                for k, tgt in enumerate(pending):
                    items.append((no, cap, tgt))
                pending = []
    for tgt in pending:
        items.append((None, None, tgt))
    out = []
    for no, cap, tgt in items:
        data = z.read("word/" + tgt)
        dst = outdir / Path(tgt).name
        dst.write_bytes(data)
        out.append((no, cap, dst))
    return out


def process(src: Path, outroot: Path, key: str):
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
    elif im.mode == "L":
        im = im.convert("RGB")
    w, h = im.size
    sizes = {}
    for label, target in (("t", W_THUMB), ("v", W_VIEW)):
        tw = min(target, w)
        th = round(h * tw / w)
        r = im.resize((tw, th), Image.LANCZOS) if tw != w else im
        dst = outroot / f"{key}-{label}.webp"
        r.save(dst, "WEBP", quality=QUALITY, method=6)
        sizes[label] = (tw, th)
    return (w, h), sizes, ahash(im)


def main(album: str, docx: str):
    album = Path(album)
    docx = Path(docx)
    pub = Path("public/photos")
    orig = Path("originals/photos")
    data = Path("src/data")
    for d in (pub, orig, data, Path("docs")):
        d.mkdir(parents=True, exist_ok=True)
    T0 = time.time()
    cache_f = orig.parent / "photo_cache.json"  # originals/ не потрапляє в git
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {"md5": {}, "proc": {}}

    # ---- збір кандидатів: (theme, section, caption, caption_source, path, order_key)
    cands = []
    for p in sorted(album.rglob("*"), key=lambda x: natural(str(x))):
        if not p.is_file() or p.suffix.lower() not in IMG_EXT or p.name.startswith(("~", "._")):
            continue
        rel = p.relative_to(album)
        late = WORK_DIR in str(rel)  # робоча папка автора: обробляємо останньою, щоб дублікати 6.5.x лишились у своїх розділах
        parts = rel.parts
        theme = section = None
        if len(parts) == 1:
            for pref, th in ROOT_THEME.items():
                if p.name.startswith(pref):
                    theme = th
            theme = theme or "okremi"
        else:
            for pref, th in FOLDER_THEME:
                if parts[0].startswith(pref):
                    theme = th
            if theme == "sviata":
                for k, v in SECTIONS_65.items():
                    if any(seg.startswith(k) for seg in parts):
                        section = v
                if late and "4  Чоповичі" in str(rel):
                    section = SECTION_CHOPOVYCHI
        if not theme:
            continue
        cands.append({"theme": theme, "section": section, "caption": caption_from_name(p.name),
                      "csrc": "filename", "path": p, "origin": str(rel), "no": None, "late": late})
    cands.sort(key=lambda c: c["late"])  # стабільно: робоча папка в кінці
    # docx «Вибране»: перші три зображення (підписи 01–03) — карти й план, далі 1…72 — екскурсія селом
    tmpdir = orig.parent / "vybrane-extracted"
    for idx, (no, cap, path) in enumerate(docx_images(docx, tmpdir)):
        cands.append({"theme": "karty" if idx < 3 else "ekskursiia", "section": None, "caption": cap,
                      "csrc": "docx", "path": path, "origin": "Вибране з фотоальбому.docx", "no": no})

    # ---- дедуплікація: точні копії в межах однієї теми зливаємо; між темами фото може повторюватися
    for c in cands:
        st = c["path"].stat()
        ck = f"{c['path']}|{st.st_size}|{int(st.st_mtime)}"
        if ck not in cache["md5"]:
            cache["md5"][ck] = md5(c["path"])
        c["md5"] = cache["md5"][ck]
    cache_f.write_text(json.dumps(cache))
    docx_cap = {c["md5"]: (c["caption"], c["no"]) for c in cands if c["csrc"] == "docx" and c["caption"]}
    kept = []
    seen = {}
    dups = []
    for c in cands:
        k = (c["md5"], c["theme"])
        if k in seen:
            keep = seen[k]
            dups.append((c["origin"], keep["origin"], c["path"].name))
            if not keep["caption"] and c["caption"]:
                keep["caption"], keep["csrc"] = c["caption"], c["csrc"]
            continue
        seen[k] = c
        kept.append(c)
    for c in kept:
        if c["md5"] in docx_cap and c["csrc"] != "docx":
            c["caption"], _ = docx_cap[c["md5"]]
            c["csrc"] = "docx"

    # ---- обробка (кожен унікальний файл один раз)
    done = {}
    ahashes = []
    for c in kept:
        key = c["md5"][:10]
        if key not in done:
            ext = c["path"].suffix.lower()
            pr = cache["proc"].get(key)
            if pr and (pub / f"{key}-t.webp").exists() and (pub / f"{key}-v.webp").exists() and (orig / f"{key}{ext}").exists():
                done[key] = dict(w=pr["w"], h=pr["h"], sizes={k: tuple(v) for k, v in pr["sizes"].items()}, ext=ext, ahash=pr["ahash"])
            else:
                if time.time() - T0 > 140:  # команда має вкластися в ліміт часу: просто запустити ще раз
                    cache_f.write_text(json.dumps(cache))
                    print(f"ЧАСТКОВО: оброблено {len(done)} з {len(set(x['md5'] for x in kept))}, запустіть ще раз")
                    sys.exit(3)
                (w, h), sizes, ah = process(c["path"], pub, key)
                shutil.copy2(c["path"], orig / f"{key}{ext}")
                done[key] = dict(w=w, h=h, sizes=sizes, ext=ext, ahash=ah)
                cache["proc"][key] = dict(w=w, h=h, sizes=sizes, ahash=ah)
            ahashes.append({"key": key, **done[key], "origin": c["origin"], "name": c["path"].name, "theme": c["theme"]})
        c.update(key=key, **{k: v for k, v in done[key].items() if k != "ahash"})

    cache_f.write_text(json.dumps(cache))
    for f in pub.glob("*.webp"):
        if f.name.split("-")[0] not in done:
            f.unlink()

    # ---- схожі (не точні) фото: тільки повідомляємо
    near = []
    for i in range(len(ahashes)):
        for j in range(i + 1, len(ahashes)):
            a, b = ahashes[i], ahashes[j]
            if bin(a["ahash"] ^ b["ahash"]).count("1") <= 3 and abs(a["w"] / a["h"] - b["w"] / b["h"]) < 0.03:
                near.append((a, b))

    # ---- порядок: за темою; docx — за номером; решта за назвою
    out_themes = []
    for slug, ref, title in THEMES:
        items = [c for c in kept if c["theme"] == slug]
        if not items:
            continue
        if slug == "ekskursiia":
            items.sort(key=lambda c: (c["no"] or 999))
        elif slug == "karty":
            items.sort(key=lambda c: (c["csrc"] != "docx", c["no"] or 0, natural(c["origin"])))
        else:
            sec_order = list(SECTIONS_65.values()) + [SECTION_CHOPOVYCHI]
            items.sort(key=lambda c: ((sec_order.index(c["section"]) if c["section"] in sec_order else -1),
                                      natural(c["path"].name)))
        plist = []
        for c in items:
            e = {
                "id": c["key"], "w": c["w"], "h": c["h"],
                "tw": c["sizes"]["t"][0], "th": c["sizes"]["t"][1],
                "vw": c["sizes"]["v"][0], "vh": c["sizes"]["v"][1],
                "caption": fix_caption(c["caption"]), "captionSource": c["csrc"] if c["caption"] else None,
                "ext": c["ext"],
            }
            if c["section"]:
                e["section"] = c["section"]
            if c["no"] is not None and slug == "ekskursiia":
                e["no"] = c["no"]
            plist.append(e)
        out_themes.append({"slug": slug, "ref": ref, "title": title, "photos": plist})

    Path("src/data/photos.json").write_text(
        json.dumps({"themes": out_themes}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- TODO
    total = sum(len(t["photos"]) for t in out_themes)
    nocap = [(t["title"], p) for t in out_themes for p in t["photos"] if not p["caption"]]
    lines = ["# TODO по фото\n",
             f"Опубліковано фото: {total}. Без підпису: {len(nocap)}. Підписи не вигадуємо: їх даємо лише з docx автора й назв файлів.\n",
             "## Точні дублікати в межах теми (не опубліковані двічі)\n"]
    lines += [f"- {n}: {a} ≡ {b}" for a, b, n in dups] or ["Немає."]
    lines += ["\n## Схожі фото (різний розмір чи обрізання): перевірити, чи не лишити одне\n"]
    lines += [f"- {a['theme']}: {a['name']} ≈ {b['theme']}: {b['name']}" for a, b in near] or ["Немає."]
    cnt = {t["slug"]: len(t["photos"]) for t in out_themes}
    lines += ["\n## Перевірити\n",
              "- 6.5.6: у книзі «8 травня 2018 року», у назві папки «9 травня 2018 р». Уточнити дату",
              f"- Кількість за описом книги: 6.3 — 34 фото (на сайті {cnt.get('ferma', 0)}), 6.4 — 31 (на сайті {cnt.get('pobut', 0)})",
              f"- Секція «{SECTION_CHOPOVYCHI}» (6.5): ці фото були лише в робочій папці автора «{WORK_DIR}», "
              "у книзі для них розділу немає. Уточнити розділ книги, підписи й дати",
              "\n## Фото без підпису\n"]
    fn = [(t["title"], p) for t in out_themes for p in t["photos"] if p["captionSource"] == "filename"]
    lines2 = ["\n## Підписи з назв файлів (автор набирав їх сам): перевірити правопис\n"]
    lines2 += [f"- {p['id']}: {p['caption']}" for _, p in fn]
    cur = None
    for title, p in nocap:
        if title != cur:
            lines.append(f"\n### {title}")
            cur = title
        lines.append(f"- {p['id']}")
    lines += lines2
    Path("docs/photos-todo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Тем: {len(out_themes)}, фото: {total}, дублікатів: {len(dups)}, схожих: {len(near)}, без підпису: {len(nocap)}")
    for t in out_themes:
        print(f"  {t['slug']:18s} {len(t['photos'])}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
