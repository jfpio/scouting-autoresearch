import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const repository = 'https://github.com/jfpio/scouting-autoresearch';
const publicSite = 'https://jfpio.github.io/scouting-autoresearch';

export default defineConfig({
  site: 'https://jfpio.github.io',
  base: '/scouting-autoresearch',
  integrations: [
    starlight({
      title: 'Scouting Autoresearch',
      description: 'Otwarta, dwujęzyczna baza historycznych gier i prób harcerskich.',
      customCss: ['./src/styles/site.css'],
      locales: {
        root: { label: 'Polski', lang: 'pl' },
        en: { label: 'English', lang: 'en' },
      },
      social: [{ icon: 'github', label: 'GitHub', href: repository }],
      editLink: { baseUrl: `${repository}/edit/main/` },
      lastUpdated: true,
      pagination: true,
      credits: true,
      head: [
        { tag: 'meta', attrs: { property: 'og:type', content: 'website' } },
        { tag: 'meta', attrs: { property: 'og:site_name', content: 'Scouting Autoresearch' } },
        { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary' } },
        {
          tag: 'link',
          attrs: {
            rel: 'alternate',
            type: 'text/plain',
            title: 'LLM index',
            href: `${publicSite}/llms.txt`,
          },
        },
      ],
      sidebar: [
        {
          label: 'Baza',
          translations: { en: 'Database' },
          items: [
            { slug: 'index' },
            { slug: 'all' },
            { slug: 'games' },
            { slug: 'trials' },
            { slug: 'sources' },
            { slug: 'about' },
          ],
        },
      ],
    }),
  ],
});
