import { describe, expect, it } from 'vitest';

describe('release link configuration', () => {
  it('represents unconfigured release URLs as explicit preview states', async () => {
    const { createReleaseLinks } = await import('./release-links');
    const links = createReleaseLinks({});
    expect(links.slice(0, 3).map((link) => link.target)).toEqual([
      { kind: 'coming-soon', url: null, previewLabel: '即将开放' },
      { kind: 'coming-soon', url: null, previewLabel: '即将开放' },
      { kind: 'coming-soon', url: null, previewLabel: '即将开放' },
    ]);
    expect(links[3].target).toEqual({ kind: 'available', url: '#english-summary' });
  });

  it('accepts configured HTTPS release links without inventing an address', async () => {
    const { createReleaseLinks } = await import('./release-links');
    const links = createReleaseLinks({ VITE_DEMO_URL: 'https://demo.example.com/' });
    expect(links[0].target).toEqual({ kind: 'available', url: 'https://demo.example.com/' });
  });

  it.each(['javascript:alert(1)', 'ftp://example.com', 'https://user:secret@example.com', '/missing-release'])
  ('rejects unsafe or incomplete configured release URL %s', async (url) => {
    const { createReleaseLinks } = await import('./release-links');
    expect(() => createReleaseLinks({ VITE_DEMO_URL: url })).toThrow(/VITE_DEMO_URL/);
  });
});
