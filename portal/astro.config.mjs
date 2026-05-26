// @ts-check
import { defineConfig } from 'astro/config';
import { fileURLToPath } from 'node:url';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://platform.odap.local',
  output: 'static',
  build: {
    format: 'directory',
  },
  // React integration powers the v2 shell's interactive islands
  // (CommandPalette, NotificationBell, PersonaSwitcher) in fase 2+.
  // Astro pages stay .astro by default — React is opt-in per file.
  integrations: [mdx(), react()],
  server: {
    host: true,
    port: 4321,
  },
  vite: {
    server: {
      fs: { allow: ['..', '../..'] },
    },
    resolve: {
      alias: {
        // Single-source-of-truth alias voor canonical docs/ inhoud.
        // - Lokaal: <repo>/docs/  (één boven portal/)
        // - In Docker: /docs/  (Dockerfile COPY's docs/ daar naartoe
        //   omdat WORKDIR /app de portal-contents bevat)
        // Astro-pages kunnen zo `import { Content } from '@docs/foo.md'`
        // doen zonder fragiele ../../../-paden.
        '@docs': fileURLToPath(new URL('../docs', import.meta.url)),
      },
    },
  },
});
