// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// Сторінки-заглушки: не потрапляють у sitemap, поки не наповнені.
const stubs = ['/memorial/', '/video/', '/podilytysya/'];

export default defineConfig({
  site: 'https://lypliany-spohady.com.ua',
  trailingSlash: 'always',
  integrations: [
    sitemap({ filter: (page) => !stubs.some((s) => page.endsWith(s)) }),
  ],
  vite: { plugins: [tailwindcss()] },
});
