import { existsSync, statSync } from 'node:fs';

// PDF книги кладеться в public/download/ і з'являється на сайті автоматично після деплою.
const FILE = 'lypliany-spohady-kniha.pdf';
const path = new URL(`../../public/download/${FILE}`, import.meta.url);

export const bookPdf = existsSync(path)
  ? {
      href: `/download/${FILE}`,
      sizeMb: Math.max(1, Math.round(statSync(path).size / 1024 / 1024)),
    }
  : null;
