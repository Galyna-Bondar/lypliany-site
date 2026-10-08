# lypliany-site

Сайт-книга «Село Липляни Житомирської області у спогадах старожилів»
(Б. Ю. Лещенко, Н. М. Біла, Київ, 2026).

Адреса: https://lypliany-spohady.com.ua

## Технології

Astro 5 (статичний сайт) + Tailwind CSS 4. Розділи книги: Markdown у `src/content/book/`.
Хостинг: Cloudflare Pages (автодеплой із гілки `main`). Домен і DNS: Cloudflare.

## Команди

```
npm install        # один раз
npm run dev        # локальний перегляд на http://localhost:4321
npm run build      # збірка в dist/
```

Потрібен Node 22 (див. `.nvmrc`).

## Cloudflare Pages

- Build command: `npm run build`
- Build output directory: `dist`
- Змінна середовища: `NODE_VERSION=22`

## Книга

Текст не редагується вручну без потреби. Розбивка docx на розділи:

```
pandoc "<книга>.docx" -t markdown --wrap=none --extract-media=media -o book.md
python3 scripts/split_book.py book.md src/content/book
```

Технічні виправлення після конвертації записуються в `docs/book-changes.md`,
питання до автора (авторство підрозділів, розбіжності заголовків) у `docs/book-todo.md`.
Скрипт перезаписує всі файли в `src/content/book`, тому правки тексту вносяться в docx і розбиття запускається знову.

## PDF книги

1. Фінальний PDF (з ISBN) з Word зберегти як `book.pdf`.
2. Додати клікабельний зміст і закладки (потрібні `poppler-utils` і `pikepdf`):
   `python3 scripts/pdf_toc.py book.pdf public/download/lypliany-spohady-kniha.pdf`
3. Закомітити й запушити. Кнопка «Скачати книгу (PDF)» на головній і в змісті з'явиться сама, коли файл існує.
Вихідні матеріали (оригінали фото, аудіо, відео) в репозиторій не кладемо
(`materials/`, `originals/` ігноруються).

## Стан

- [x] Каркас, дизайн (варіант A «Хата й рушник»), головна, зміст, читалка, «Про книгу»
- [x] Розділи 1–5 книги (48 сторінок), розділ 6 піде в галереї
- [ ] Остаточний PDF книги з ISBN і клікабельним змістом
- [ ] Фото й галереї
- [ ] Аудіо (Cloudflare R2) і відео (YouTube)
- [ ] Меморіал, покажчик, пошук (Pagefind)
- [ ] Переадресація `/media` на Google Диск (Cloudflare Redirect Rules)
