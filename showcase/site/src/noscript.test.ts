import { afterEach, describe, expect, it, vi } from 'vitest';
import { build } from 'vite';

afterEach(() => vi.unstubAllEnvs());

async function builtHtml() {
  const result = await build({ logLevel: 'silent', build: { write: false } });
  const bundle = Array.isArray(result) ? result[0] : result;
  if (!('output' in bundle)) throw new Error('Expected an in-memory bundle');
  const html = bundle.output.find((file) => file.type === 'asset' && file.fileName === 'index.html');
  if (!html || html.type !== 'asset') throw new Error('Expected the HTML asset');
  return String(html.source);
}

describe('English summary without JavaScript', () => {
  it('includes a substantive summary and avoids unavailable fragment destinations', async () => {
    const html = await builtHtml();
    const summary = html.match(/<noscript>[\s\S]*?<\/noscript>/)?.[0] ?? '';
    expect(summary).toContain('lang="en"');
    expect(summary).toContain('Personal showcase maintenance');
    expect(summary).toContain('Tool Calling');
    expect(summary).toContain('FastAPI, PostgreSQL');
    expect(summary).toContain('Fictional data and simulated transactions');
    expect(summary).toContain('Public URLs and the walkthrough are being prepared');
    expect(summary).not.toMatch(/href="#/);
  });

  it('uses configured public URLs safely in the built summary', async () => {
    vi.stubEnv('VITE_DEMO_URL', 'https://demo.example.com/?a=1&b=2');
    const html = await builtHtml();
    const summary = html.match(/<noscript>[\s\S]*?<\/noscript>/)?.[0] ?? '';
    expect(summary).toContain('href="https://demo.example.com/?a=1&amp;b=2"');
    expect(summary).toContain('Live demo');
    expect(summary).toContain('aria-label="Live demo · Open the Workshop AI live demo"');
  });
});
