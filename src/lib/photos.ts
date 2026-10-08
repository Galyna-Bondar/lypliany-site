import data from '../data/photos.json';

export type Photo = {
  id: string; w: number; h: number; tw: number; th: number; vw: number; vh: number;
  caption: string | null; captionSource: 'docx' | 'filename' | null;
  ext: string; section?: string; no?: number;
};
export type Theme = { slug: string; ref: string; title: string; photos: Photo[] };

export const themes = data.themes as Theme[];

// Оригінали (повний розмір) лежатимуть у Cloudflare R2. Коли бакет буде підключений до домену,
// вписати сюди адресу, наприклад 'https://media.lypliany-spohady.com.ua/photos'.
// Поки порожньо, кнопка «Оригінал» не показується.
export const ORIGINALS_BASE = '';

export const thumb = (p: Photo) => `/photos/${p.id}-t.webp`;
export const view = (p: Photo) => `/photos/${p.id}-v.webp`;
export const original = (p: Photo) => (ORIGINALS_BASE ? `${ORIGINALS_BASE}/${p.id}${p.ext}` : null);

export const countLabel = (n: number) => `${n} фото`;
