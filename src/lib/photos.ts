import data from '../data/photos.json';

export type Photo = {
  id: string; w: number; h: number; tw: number; th: number; vw: number; vh: number;
  caption: string | null; captionSource: 'docx' | 'filename' | null;
  ext: string; section?: string; no?: number;
};
export type Theme = { slug: string; ref: string; title: string; photos: Photo[] };

export const themes = data.themes as Theme[];

// Оригінали (повний розмір) лежать у Cloudflare R2: media.lypliany-spohady.com.ua/photos/<id><ext>
import { MEDIA_BASE } from './media';
export const ORIGINALS_BASE = `${MEDIA_BASE}/photos`;

export const thumb = (p: Photo) => `/photos/${p.id}-t.webp`;
export const view = (p: Photo) => `/photos/${p.id}-v.webp`;
export const original = (p: Photo) => (ORIGINALS_BASE ? `${ORIGINALS_BASE}/${p.id}${p.ext}` : null);

export const countLabel = (n: number) => `${n} фото`;
