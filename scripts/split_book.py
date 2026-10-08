#!/usr/bin/env python3
"""
Розбиває Markdown книги (pandoc docx -> md) на файли підрозділів для сайту.

Використання (з кореня репозиторію, потрібен pandoc):
  pandoc "<книга>.docx" -t markdown --wrap=none --extract-media=media -o book.md
  python3 scripts/split_book.py book.md src/content/book

Текст не переписується. Дозволені лише технічні дії, які записуються у
docs/book-changes.md: виправлення службових символів, відновлення нумерації
заголовків, перетворення заголовків на Markdown-заголовки, перетворення таблиць.
Розбіжності та сумнівні місця записуються у docs/book-todo.md.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

CH1 = "Розділ 1. Наш край з давніх-давен"
CH2 = "Розділ 2. Село Липляни в 20 столітті"
CH3 = "Розділ 3. Історія у спогадах і долях селян"
CH4 = "Розділ 4. Відомі люди села"
CH5 = "Розділ 5. Меморіал"
LB = "Лещенко Б. Ю."
BN = "Біла Н. М."

# Автори: зі змісту книги. Якщо у змісті автор підрозділу не вказаний, береться автор розділу
# (див. docs/book-todo.md, там це позначено для підтвердження).
# (number, title, part, authors, authors_explicit)
# Особливі початки задаються окремо у START_OVERRIDE.
BODY_SECTIONS = [
    ("1.1", "Від Льодовикової епохи до утворення племен", CH1, [LB], False),
    ("1.2", "Держава (Київська) Русь з 882-го року", CH1, [LB], False),
    ("1.3", "Напад татаро-монголів на чолі з Батиєм у 1240 році на східно-європейських слов'ян", CH1, [LB], False),
    ("1.4", "Велике Князівство Литовське з початку 14 століття", CH1, [LB], False),
    ("1.5", "Українське козацтво виникло в кінці 15 століття", CH1, [LB], False),
    ("1.6", "Польсько-Литовська держава з 1569 року (Річ Посполита)", CH1, [LB], False),
    ("1.7", "Російсько-польські війни", CH1, [LB], False),
    ("1.8", "Українська Народна Республіка 1917 – 1921 рр.", CH1, [LB], False),
    ("1.9", "Карти України", CH1, [LB], False),
    ("2.1", "Початок 20-го століття", CH2, [BN], False),
    ("2.2", "Війна. Село в окупації 1941 – 1943 рр.", CH2, [LB], True),
    ("2.3", "Після війни", CH2, [BN], False),
    ("BOUNDARY", "2.4"),
    ("2.4.1", "Післявоєнне лихоліття", CH2, [BN], False),
    ("2.4.2", "Наш Паша", CH2, [BN], False),
    ("2.4.3", "Ступа й жорна – біда чорна", CH2, [BN], False),
    ("2.4.4", "Корова не кінь", CH2, [BN], False),
    ("2.4.5", "Машинно-тракторні станції МТС", CH2, [LB, BN], True),
    ("2.4.6", "Колгоспне життя", CH2, [BN], False),
    ("2.4.7", "Сусіди", CH2, [BN], False),
    ("2.4.8", "Сусіди-чехи", CH2, [LB, BN], True),
    ("3.1", "Голодомор", CH3, [BN], False),
    ("3.2", "Рід Макомацьких", CH3, [LB], True),
    ("3.3", "Моя мама", CH3, [LB], True),
    ("3.4", "Шкільні роки", CH3, [LB], True),
    ("3.5", "В'яз поруч із людьми", CH3, [BN], False),
    ("3.6.1", "Археологічна знахідка 15 століття в селі Липляни", CH3, [LB], True),
    ("3.6.2", "Ікона з церкви в селі Липляни", CH3, [LB], True),
    ("3.7", "Доброта людей спасла життя", CH3, [LB, BN], True),
    ("3.8", "Христя", CH3, [BN], False),
    ("3.9", "На ярмарок!", CH3, [BN], False),
    ("3.10", "Родина", CH3, [BN], False),
    ("3.11", "В селі новини швидко розходяться", CH3, [BN], False),
    ("3.12", "Село моє рідне", CH3, [BN], False),
    ("3.13", "Урочища", CH3, [LB, BN], True),
    ("3.14", "Пам'ять", CH3, [BN], False),
    ("3.15", "Сповідь", CH3, [BN], False),
    ("3.16", "Сімейний подарунок", CH3, [BN], False),
    ("4", "Відомі люди села", CH4, [LB, BN], True),
    ("5.1", "Лист-пропозиція", CH5, [LB], False),
    ("5.2", "Список жителів с. Липляни, яких німці вивезли в 1942-43 роках у Німеччину на примусові роботи", CH5, [LB], False),
    ("5.3", "Список захоронених у братській могилі с. Йосипівка в роки Другої світової війни", CH5, [LB], False),
    ("5.4", "Список військових ветеранів", CH5, [LB], False),
    ("5.5", "Список військовослужбовців, партизан, підпільників, які загинули в боях і пропали безвісти в роки Другої світової війни, по селу Липляни", CH5, [LB], False),
    ("5.6", "Список учасників війни, які померли після війни, на с. Липляни", CH5, [LB], False),
    ("5.7", "Список військовослужбовців, партизан, підпільників, які загинули в боях і пропали безвісти в роки Другої світової війни, по селу Йосипівка", CH5, [LB], False),
    ("5.8", "Список учасників війни, які померли після війни, по селу Йосипівка", CH5, [LB], False),
]

# Спеціальні початки (у docx нумерація цих заголовків перетворилась на автонумерований список)
START_OVERRIDE = {
    "1.7": r"^7\.\s+\*\*\. Російсько-польські війни\*\*$",
    "1.8": r"^7\.\s+\*\*Українська Народна Республіка 1917",
    "4": r"^> \*\*Розділ 4\.",
}
# Рядки-«підзаголовки», які pandoc перетворив на автонумерований список: (regex, новий заголовок)
LIST_HEADINGS = [
    (re.compile(r"^2\.\s+\*\*Російсько-польська війна 1792\*\*$"), "## 1.7.2. Російсько-польська війна 1792"),
]
# Скільки непорожніх рядків після заголовка належать самому заголовку (продовження назви)
HEADING_CONTINUATION = {"5.2": 1, "5.3": 2, "5.5": 1, "5.6": 1, "5.7": 1, "5.8": 2}

# Імена файлів, що вже були опубліковані
SLUG_OVERRIDE = {"1.1": "1-1-lodovykova-epokha"}

# Назви фото в тексті книги (джерело — витягнуті pandoc медіа) -> публічний шлях
IMAGES = {
    "media/media/image2.jpeg": "/book/image2.webp",
}

FIXES = [
    (re.compile(r"\\'"), "'", "Прибрано службове екранування апострофа (\\') після конвертації з docx"),
    (re.compile(r"\s*̶\s*"), " – ", "Символ U+0336 (перекреслення), яким у docx набрано тире, замінено на звичайне тире «–»"),
]

UA = dict(zip("абвгґдезийклмнопрстуфцчшщьюяіїє",
              ["a","b","v","h","g","d","e","z","y","i","k","l","m","n","o","p","r","s","t","u","f","ts","ch","sh","shch","","iu","ia","i","i","ie"]))
UA.update({"ж": "zh", "х": "kh", "ь": ""})
UA["и"] = "y"; UA["й"] = "i"


def translit(s: str) -> str:
    out = "".join(UA.get(c, c) for c in s.lower())
    return re.sub(r"[^a-z0-9]+", "-", out).strip("-")


def make_slug(number: str, title: str) -> str:
    if number in SLUG_OVERRIDE:
        return SLUG_OVERRIDE[number]
    words = translit(title).split("-")[:4]
    return "-".join([number.replace(".", "-")] + words)


def num_rx(n: str) -> re.Pattern:
    return re.compile(r"^(?:> )?\*{2,3}" + re.escape(n) + r"(?:\.?\s|\.?\*)")


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def clean_heading(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("> ", "", 1).replace("*", "")).strip()


def find_after(lines, rx, after):
    for i in range(after + 1, len(lines)):
        if rx.match(lines[i].strip() if rx.pattern.startswith("^7") or rx.pattern.startswith("^2") else lines[i]):
            return i
    raise SystemExit(f"Не знайдено початок за шаблоном {rx.pattern!r} після рядка {after}")


def convert_tables(body: str) -> tuple[str, bool]:
    if not re.search(r"^\+[-=+]+\+$", body, re.M):
        return body, False
    r = subprocess.run(["pandoc", "-f", "markdown", "-t", "gfm", "--wrap=none"],
                       input=body, capture_output=True, text=True, check=True)
    return r.stdout, True


def main(src: str, outdir: str) -> None:
    lines = Path(src).read_text(encoding="utf-8").splitlines()
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.md"):
        f.unlink()
    changes = {}   # note -> {slug: n}
    todo = []

    def note(msg, slug, n=1):
        changes.setdefault(msg, {})
        changes[msg][slug] = changes[msg].get(slug, 0) + n

    # ---- Вступні сторінки (початки за точним рядком, як і раніше)
    def last_idx(text):
        idx = [i for i, l in enumerate(lines) if l.strip() == text]
        if not idx:
            raise SystemExit(f"Не знайдено: {text!r}")
        return idx[-1]

    chapter_rx = re.compile(r"^> \*\*Розділ \d")
    ch1_line = last_idx("> **Розділ 1. Наш край з давніх-давен**")
    entries = []  # (slug, number, title, part, authors, explicit, start, end, order, cont)
    pre = [
        ("peredmova", None, "Передмова", "Вступ", [LB], True, last_idx("**Передмова**")),
        ("adminustrii", None, "Адміністративно-територіальний устрій села", "Вступ", [LB], True,
         last_idx("**Адміністративно-територіальний устрій села Липляни**")),
    ]
    starts = []  # all boundaries: (start_idx, kind, payload)
    for slug, number, title, part, authors, explicit, s in pre:
        starts.append((s, "sec", (slug, number, title, part, authors, explicit, 0)))

    prev = ch1_line
    for item in BODY_SECTIONS:
        if item[0] == "BOUNDARY":
            s = next(i for i in range(prev + 1, len(lines)) if num_rx(item[1]).match(lines[i]))
            starts.append((s, "bound", item[1]))
            prev = s
            continue
        number, title, part, authors, explicit = item
        pat = START_OVERRIDE.get(number)
        if pat:
            rx = re.compile(pat)
            s = next((i for i in range(prev + 1, len(lines)) if rx.match(lines[i])), None)
        else:
            rx = num_rx(number)
            s = next((i for i in range(prev + 1, len(lines)) if rx.match(lines[i])), None)
        if s is None:
            raise SystemExit(f"Не знайдено початок {number} {title}")
        starts.append((s, "sec", (make_slug(number, title) if number != "4" else "4-vidomi-liudy-sela",
                                  number if number != "4" else None, title, part, authors, explicit,
                                  HEADING_CONTINUATION.get(number, 0))))
        prev = s
    starts.sort(key=lambda x: x[0])

    order = 10
    log_counts = []
    for k, (s, kind, payload) in enumerate(starts):
        if kind != "sec":
            continue
        slug, number, title, part, authors, explicit, cont = payload
        # кінець: наступна межа або заголовок розділу
        e = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        for j in range(s + 1, e):
            if chapter_rx.match(lines[j]):
                e = j
                break
        head_line = lines[s]
        seg = lines[s + 1:e]

        # продовження заголовка (в окремих рядках)
        if cont:
            dropped = 0
            idx = 0
            while idx < len(seg) and dropped < cont:
                t = seg[idx].strip()
                if t in ("", ">"):
                    idx += 1
                    continue
                idx += 1
                dropped += 1
            removed = [x for x in seg[:idx] if x.strip() not in ("", ">")]
            seg = seg[idx:]
            note("Рядки, які були продовженням заголовка підрозділу (розірваного на кілька рядків у docx), прибрано з тексту й перенесено в заголовок сторінки", slug, len(removed))

        # підзаголовки
        body_lines = []
        n_sub = 0
        for l in seg:
            matched = False
            for rx2, repl in LIST_HEADINGS:
                if rx2.match(l):
                    body_lines.append(repl)
                    note("Відновлено нумерацію заголовків, яку Word перетворив на автосписок", slug)
                    matched = True
                    break
            if matched:
                continue
            raw = l.replace("> ", "", 1) if l.startswith("> ") else l
            if "**" in raw and len(raw) < 140:
                plain = re.sub(r"\s+", " ", raw.replace("*", "")).strip()
                m = re.match(r"^(\d+\.\d+\.\d+)\.?\s+(\S.*)$", plain)
                if m:
                    body_lines.append(f"## {m.group(1)}. {m.group(2)}")
                    n_sub += 1
                    continue
            body_lines.append(l)
        if n_sub:
            note("Жирні рядки-підзаголовки (x.y.z) оформлено як Markdown-заголовки другого рівня (текст заголовків не змінено)", slug, n_sub)
        body = "\n".join(body_lines).strip() + "\n"

        # заголовок із додатковим текстом (3.3) → перший абзац
        hc = clean_heading(head_line)
        hc_nonum = re.sub(r"^(?:Розділ\s+)?\d+(\.\d+)*\.?\s*", "", hc)
        if number and norm(hc_nonum).startswith(norm(title)) and len(norm(hc_nonum)) > len(norm(title)) + 5:
            rest = hc_nonum[len(title):].strip() if hc_nonum.startswith(title) else None
            if rest:
                body = f"*{rest}*\n\n" + body
                note("Частину заголовка, що містила імена й роки, винесено в перший абзац сторінки", slug)
        elif number or slug == "4-vidomi-liudy-sela":
            if norm(hc_nonum) != norm(title) and not norm(title).startswith(norm(hc_nonum)) and not norm(hc_nonum).startswith(norm(title)):
                todo.append(f"- {number or 'Розділ 4'}: у змісті «{title}», у тексті «{hc_nonum}». Залишено як у змісті; уточнити, яку редакцію лишити")

        for rx, repl, nt in FIXES:
            body, n = rx.subn(repl, body)
            if n:
                note(nt, slug, n)

        # зображення з docx
        def img(m):
            path = m.group(1)
            if path in IMAGES:
                note("Зображення з docx винесено в окремий файл (WebP), прибрано розміри з docx", slug)
                return f"![Рукописна схема села з пронумерованими об'єктами (перелік об'єктів нижче)]({IMAGES[path]})"
            todo.append(f"- {slug}: зображення {path} не оброблено")
            return m.group(0)
        body = re.sub(r"!\[\]\(([^)]+)\)(?:\{[^}]*\})?", img, body)

        body, tbl = convert_tables(body)
        if tbl:
            note("Таблиці з docx (текстовий формат pandoc) перетворено на HTML/GFM-таблиці; зміст комірок не змінено", slug)

        fm = ["---", f"title: {json.dumps(title, ensure_ascii=False)}", f"part: {json.dumps(part, ensure_ascii=False)}"]
        if number:
            fm.append(f'number: "{number}"')
        fm.append(f"order: {order}")
        fm.append("authors: [" + ", ".join(json.dumps(a, ensure_ascii=False) for a in authors) + "]")
        fm.append("---\n")
        (out / f"{slug}.md").write_text("\n".join(fm) + "\n" + body, encoding="utf-8")
        print(f"{order:4d} {slug}: {len(body.split())} слів")
        if not explicit and part != "Вступ":
            log_counts.append(f"{number or 'Розділ 4'}")
        order += 10

    log = ["# Перелік технічних змін у тексті книги\n",
           "Зміст книги не змінювався. Нижче лише технічні дії після конвертації з docx.\n"]
    for nt, per in changes.items():
        total = sum(per.values())
        log.append(f"- {nt}: {total} (" + ", ".join(f"{k}: {v}" for k, v in per.items()) + ")")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/book-changes.md").write_text("\n".join(log) + "\n", encoding="utf-8")

    t = ["# TODO по змісту книги\n",
         "## Авторство підрозділів\n",
         "У змісті автор підрозділу вказаний не скрізь. Де не вказаний, на сторінці стоїть автор розділу "
         "(за правилом змісту «автор розділу, якщо не вказано інакше»). Підтвердити з Борисом Юхимовичем для підрозділів: "
         + ", ".join(log_counts) + ".\n",
         "## Розбіжності між змістом і текстом\n"] + (todo or ["Немає."]) + [
         "\n## Інше\n",
         "- 5.3: у змісті «…в роки Другої світової війни», у заголовку в тексті «…в роки Великої Вітчизняної війни». На сторінці стоїть назва зі змісту.",
         "- 3.2.3: на схемі села 16 пронумерованих об'єктів, а в переліку під нею 15 пунктів. Уточнити, чи немає пункту 16.",
         "- 3.2.3: підпис до схеми села відсутній (у docx немає), потрібна назва/підпис від автора.",
         "- Розділ 6 (Фотоальбом, Аудіозаписи) не включено в читалку: його текст піде в галереї й сторінки аудіо.",
         "- Прізвища в списках розділу 5 не перевірялись і не змінювались."]
    Path("docs/book-todo.md").write_text("\n".join(t) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
