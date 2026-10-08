#!/usr/bin/env python3
"""
Розбиває Markdown книги (pandoc docx -> md) на файли підрозділів для сайту.

Використання:
  pandoc "<книга>.docx" -t markdown --wrap=none -o book.md
  python3 scripts/split_book.py book.md src/content/book

Текст не переписується. Допускаються лише технічні виправлення, які
записуються у docs/book-changes.md (див. FIXES нижче). Запускати з кореня репозиторію.
"""
import re
import sys
from pathlib import Path

# (slug, number, title, part, authors, start_line_exact, end_line_exact_or_None, order)
SECTIONS = [
    ("peredmova", None, "Передмова", "Вступ", ["Лещенко Б. Ю."],
     "**Передмова**", "**Адміністративно-територіальний устрій села Липляни**", 10),
    ("adminustrii", None, "Адміністративно-територіальний устрій села", "Вступ", ["Лещенко Б. Ю."],
     "**Адміністративно-територіальний устрій села Липляни**", "> **Розділ 1. Наш край з давніх-давен**", 20),
    ("1-1-lodovykova-epokha", "1.1", "Від Льодовикової епохи до утворення племен",
     "Розділ 1. Наш край з давніх-давен", ["Лещенко Б. Ю."],
     "**1.1. Від Льодовикової епохи до утворення племен**", "> **1.2. Держава (Київська) Русь з 882-го року**", 110),
]

# Технічні виправлення (кожне фіксується в CHANGES.md)
FIXES = [
    # pandoc екранує апостроф: Лип\'яни -> Лип'яни
    (re.compile(r"\\'"), "'", "Прибрано службове екранування апострофа (\\') після конвертації з docx"),
    # у docx замість тире використано комбінований символ U+0336 (перекреслення),
    # що в браузері виглядає як перекреслена цифра/літера
    (re.compile(r"\s*̶\s*"), " – ", "Символ U+0336 (перекреслення), яким у docx набрано тире, замінено на звичайне тире «–»"),
]


def main(src: str, outdir: str) -> None:
    lines = Path(src).read_text(encoding="utf-8").splitlines()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    changes = {}
    for slug, number, title, part, authors, start, end, order in SECTIONS:
        # Початок: останній збіг рядка (перший може бути в змісті)
        starts = [i for i, l in enumerate(lines) if l.strip() == start]
        if not starts:
            raise SystemExit(f"Не знайдено початок: {start!r}")
        s = starts[-1]
        e = len(lines)
        if end:
            ends = [i for i in range(s + 1, len(lines)) if lines[i].strip() == end]
            if not ends:
                raise SystemExit(f"Не знайдено кінець: {end!r}")
            e = ends[0]
        body = "\n".join(lines[s + 1:e]).strip() + "\n"
        for rx, repl, note in FIXES:
            body, n = rx.subn(repl, body)
            if n:
                changes.setdefault(note, {})[slug] = n
        fm = ["---", f'title: "{title}"', f'part: "{part}"']
        if number:
            fm.append(f'number: "{number}"')
        fm.append(f"order: {order}")
        fm.append("authors: [" + ", ".join(f'"{a}"' for a in authors) + "]")
        fm.append("---\n")
        (out / f"{slug}.md").write_text("\n".join(fm) + "\n" + body, encoding="utf-8")
        print(f"{slug}: {len(body.split())} слів")

    log = ["# Перелік технічних змін у тексті книги\n",
           "Зміст не змінювався. Нижче лише технічні виправлення після конвертації з docx.\n"]
    for note, per in changes.items():
        total = sum(per.values())
        log.append(f"- {note}: {total} місць ({', '.join(f'{k}: {v}' for k, v in per.items())})")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/book-changes.md").write_text("\n".join(log) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
