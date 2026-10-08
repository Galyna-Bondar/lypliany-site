import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Розділи книги. Порядок задає поле `order`.
const book = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/book' }),
  schema: z.object({
    title: z.string(),
    // Назва розділу, до якого належить підрозділ (для змісту)
    part: z.string(),
    // Номер у змісті книги, напр. "1.1" (необов'язково)
    number: z.string().optional(),
    order: z.number(),
    authors: z.array(z.string()).default([]),
  }),
});

export const collections = { book };
