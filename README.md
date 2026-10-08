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
pandoc "<книга>.docx" -t markdown --wrap=none -o book.md
python3 scripts/split_book.py book.md src/content/book
```

Технічні виправлення після конвертації записуються в `docs/book-changes.md`.
Вихідні матеріали (оригінали фото, аудіо, відео) в репозиторій не кладемо
(`materials/`, `originals/` ігноруються).

## Стан

- [x] Каркас, дизайн (варіант A «Хата й рушник»), головна, зміст, читалка, «Про книгу»
- [x] Розділи: Передмова, Адмінустрій, 1.1
- [ ] Решта розділів книги
- [ ] Фото й галереї
- [ ] Аудіо (Cloudflare R2) і відео (YouTube)
- [ ] Меморіал, покажчик, пошук (Pagefind)
- [ ] Переадресація `/media` на Google Диск (Cloudflare Redirect Rules)
