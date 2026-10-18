#!/usr/bin/env python3
"""
Готує папку upload-r2/ для завантаження в бакет R2 (lypliany-media): лише потрібні файли, назви латиницею.
  upload-r2/photos/<id><ext>      оригінали фото (за src/data/photos.json)
  upload-r2/audio/<slug>.mp3      інтерв'ю й пісні (WMA конвертується в mp3)
Також пише docs/audio-manifest.json: slug, оригінальна назва файлу, тривалість. Імена й роки не вигадуємо.

Використання (з кореня репозиторію):
  python3 scripts/prepare_r2_upload.py "<папка ФОТОАЛЬБОМ. АУДІОЗАПИСИ-село Липляни>"
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

album = Path(sys.argv[1])
out = Path("upload-r2")
(out / "photos").mkdir(parents=True, exist_ok=True)
(out / "audio").mkdir(parents=True, exist_ok=True)

# ---- фото
data = json.loads(Path("src/data/photos.json").read_text(encoding="utf-8"))
n = 0
for t in data["themes"]:
    for p in t["photos"]:
        src = Path("originals/photos") / f"{p['id']}{p['ext']}"
        dst = out / "photos" / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        n += 1
print("фото:", n)

# ---- аудіо
def dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()))
    except ValueError:
        return None

manifest = []
def add(slug, src, kind):
    dst = out / "audio" / f"{slug}.mp3"
    if not dst.exists():
        if src.suffix.lower() == ".mp3":
            shutil.copy2(src, dst)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-codec:a", "libmp3lame", "-q:a", "4", str(dst)], check=True)
    manifest.append({"file": f"audio/{slug}.mp3", "kind": kind, "original": src.name,
                     "seconds": dur(dst), "bytes": dst.stat().st_size})

for f in sorted((album / "6.11А- Диктофон-спогади").glob("*.mp3")):
    m = re.match(r"^6\.11\.(\d+)", f.name) or re.match(r"^Стз(\d+)", f.name)
    slug = f"interview-{int(m.group(1)):02d}" if m else "interview-unlabeled-44"
    add(slug, f, "interview")
songs = sorted((album / "6.11Б-пісні, танці").iterdir(), key=lambda p: p.name)
for f in songs:
    m = re.match(r"^(\d+)\.", f.name)
    if m and f.suffix.lower() == ".mp3":
        add(f"song-{int(m.group(1)):02d}", f, "song")
    elif f.suffix.lower() == ".wma":
        add("nightingale-2012", f, "nature")
Path("docs/audio-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("аудіо:", len(manifest))
