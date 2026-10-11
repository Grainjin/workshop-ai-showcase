import { loadEnv } from 'vite';
import { configDefaults, defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { createMetadataTags } from './src/metadata';
import { createReleaseLinks } from './src/content/release-links';
import { createNoscriptSummary } from './src/noscript';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  createReleaseLinks(env);
  return {
    test: { exclude: [...configDefaults.exclude, 'e2e/**'] },
    plugins: [react(), {
      name: 'case-study-metadata',
      transformIndexHtml: (html: string) => html
        .replace('<!-- site-metadata -->', createMetadataTags(env))
        .replace('<!-- english-noscript -->', createNoscriptSummary(env)),
    }],
    build: { outDir: 'dist', sourcemap: false },
  };
});
