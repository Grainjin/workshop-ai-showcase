import { describe, expect, it } from 'vitest';

describe('static preview metadata', () => {
  it('provides meaningful local preview metadata without a fabricated canonical URL', async () => {
    const { createMetadataTags } = await import('./metadata');
    const tags = createMetadataTags({});
    expect(tags).toContain('property="og:title"');
    expect(tags).toContain('property="og:description"');
    expect(tags).toContain('content="/social-preview.png"');
    expect(tags).not.toContain('rel="canonical"');
  });

  it('uses the environment canonical URL and resolves the share image against it', async () => {
    const { createMetadataTags } = await import('./metadata');
    const tags = createMetadataTags({ VITE_CANONICAL_URL: 'https://example.com/case-study/' });
    expect(tags).toContain('rel="canonical" href="https://example.com/case-study/"');
    expect(tags).toContain('property="og:url" content="https://example.com/case-study/"');
    expect(tags).toContain('content="https://example.com/social-preview.png"');
  });

  it('rejects an invalid canonical URL rather than publishing misleading metadata', async () => {
    const { createMetadataTags } = await import('./metadata');
    expect(() => createMetadataTags({ VITE_CANONICAL_URL: 'not-a-url' })).toThrow(/VITE_CANONICAL_URL/);
  });
});
