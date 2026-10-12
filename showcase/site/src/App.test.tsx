import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import App from './App';

const render = () => renderToStaticMarkup(<App />);
const section = (html: string, id: string) => html.match(new RegExp(`<section[^>]*id="${id}"[\\s\\S]*?</section>`))?.[0] ?? '';
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe('product introduction visitor paths', () => {
  // Broken destinations, omitted download/contact actions and lost product evidence
  // are consumer-visible breaks; exact prose is deliberately not frozen here.
  it('offers a same-origin PDF download alongside the four product actions', () => {
    const overview = section(render(), 'overview');
    expect(overview).toMatch(/<a[^>]*href="\/documents\/Workshop-AI-Product-Introduction-Zhan-Jin\.pdf"[^>]*download/);
    const actions = overview.match(/<nav[^>]*aria-label="产品入口"[\s\S]*?<\/nav>/)?.[0] ?? '';
    expect(actions.match(/<a /g)).toHaveLength(4);
    expect(actions).not.toMatch(/href="(?:|#)"|aria-disabled|tabindex="-1"/);
  });
  it('gives every internal navigation/action a unique focusable destination', () => {
    const html = render();
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
    expect(new Set(ids).size).toBe(ids.length);
    for (const [, id] of html.matchAll(/href="#([^"]+)"/g)) {
      expect(html).toMatch(new RegExp(`id="${id}"[^>]*tabindex="-1"`));
    }
    expect(html).toMatch(/<main id="main-content"[^>]*tabindex="-1"/);
  });
  it('makes engineering evidence opt-in with a keyboard-accessible native disclosure', () => {
    const details = render().match(/<details class="engineering-details"[\s\S]*?<\/details>/)?.[0] ?? '';
    expect(details).toContain('<summary>');
    expect(details).not.toMatch(/<details[^>]*\bopen\b/);
    expect(details).toContain('id="architecture"');
    expect(details).toContain('id="evidence"');
  });
  it('loads six core flow captures from shipped assets with accessible captions', () => {
    const html = render();
    for (const name of ['service-search', 'provider-detail', 'booking-request', 'customer-chat', 'quote-estimate', 'provider-workbench']) {
      expect(existsSync(resolve('../assets/product', `${name}.jpg`))).toBe(true);
      expect(html).toMatch(new RegExp(`<img[^>]*src="[^"]*${name}\\.jpg[^>]*alt="[^"]{8,}"`));
    }
    const walkthrough = section(html, 'walkthrough');
    expect(walkthrough).not.toMatch(/<video|\.mp4/);
    const images = [...walkthrough.matchAll(/<img[^>]*>/g)].map(match => match[0]);
    expect(images.length).toBeGreaterThanOrEqual(6);
    for (const image of images) expect(image).toMatch(/loading="lazy"[^>]*width="\d+"[^>]*height="\d+"/);
  });
  it('shows offline AI capability evidence as accessible product media', () => {
    expect(section(render(), 'ai')).toMatch(/<img[^>]*src="[^"]*ai-capabilities\.jpg[^>]*alt="[^"]+"/);
  });
  it('offers contact and an English summary with a working return path', () => {
    const html = render();
    expect(html).toContain('href="tel:15366123264"');
    expect(html).toContain('href="mailto:jinzhan_2023@163.com"');
    const english = section(html, 'english-summary');
    expect(english).toContain('lang="en"');
    expect(english).toContain('href="#overview"');
    expect(english).not.toContain('role="dialog"');
  });
  it('routes unavailable actions to substantive on-page experience guidance', () => {
    const html = render();
    const actions = section(html, 'overview').match(/<nav[\s\S]*?<\/nav>/)?.[0] ?? '';
    expect(actions).toContain('href="#experience"');
    expect(actions).toContain('href="#walkthrough"');
    expect(section(html, 'experience')).toMatch(/<p[^>]*>[^<]{20,}<\/p>/);
  });
  it('preserves configured destinations without replacing actual product media', async () => {
    vi.stubEnv('VITE_DEMO_URL', 'https://demo.example.com/');
    vi.stubEnv('VITE_VIDEO_URL', 'https://video.example.com/');
    vi.stubEnv('VITE_GITHUB_URL', 'https://github.com/example/showcase');
    vi.resetModules();
    const { default: ConfiguredApp } = await import('./App');
    const html = renderToStaticMarkup(<ConfiguredApp />);
    for (const url of ['https://demo.example.com/', 'https://video.example.com/', 'https://github.com/example/showcase']) {
      expect(section(html, 'overview')).toContain(`href="${url}"`);
    }
    expect(section(html, 'walkthrough').match(/<img /g)?.length).toBeGreaterThanOrEqual(6);
  });
});
