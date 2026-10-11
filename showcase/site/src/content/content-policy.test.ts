import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

// Only add independently verified non-owner identities. Never infer them from aliases.
const prohibitedNames: readonly string[] = [];
const restrictedLanguage = [
  /(?<![a-z0-9])ws[-_]?\d+(?![a-z0-9]|\.\d)/i,
  /\bpr\s*#?\s*\d+\b|\/pull\/\d+\b|\bpull[ -]request\b/i,
  /\bji[r]a\b|\b(?:team(?:[ -]project|[ -]member|[ -]division)?|members?|contributors?)\b/i,
  /团[队]|成员|分工/,
  /全部由我独立|独立(?:完成|实现)(?:了)?(?:全部|所有)|sole[ -]author|entirely\s+(?:built|developed)\s+by\s+me/i,
  /\d+(?:[.,]\d+)?\s*(?:[%％]|percent\b|per\s+cent\b)|百分之\s*[零一二三四五六七八九十百\d]+/i,
  /\b(?:todo|tbd|lorem\s+ipsum|placeholder)\b|待填|占位/i,
];
const escapePattern = (name: string) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
function violatesPolicy(text: string, names: readonly string[] = prohibitedNames): boolean {
  let normalized = text;
  try { normalized = decodeURIComponent(text); } catch { /* Prose may contain a literal percent sign. */ }
  return restrictedLanguage.some((pattern) => pattern.test(normalized)) || names.some((name) =>
    new RegExp(`(?<![\\p{L}\\p{N}])${escapePattern(name)}(?![\\p{L}\\p{N}])`, 'iu').test(normalized),
  );
}
function strings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

describe('public content contract', () => {
  // Missing modules, omitted sections, broken URLs and misleading copy are consumer-visible breaks.
  it('publishes the Chinese and English content modules', () => {
    expect(existsSync(resolve('src/content/caseStudy.zh-CN.ts'))).toBe(true);
    expect(existsSync(resolve('src/content/summary.en.ts'))).toBe(true);
  });

  it('provides substantive titles and bodies for every required Chinese section', async () => {
    const { caseStudy } = await import('./caseStudy.zh-CN');
    for (const key of ['hero', 'problem', 'journey', 'aiLayer', 'decisionSupport', 'architecture',
      'showcaseEdition', 'evidence', 'limitations', 'reflection'] as const) {
      expect(caseStudy[key].title.trim().length).toBeGreaterThan(3);
      expect(caseStudy[key].body.length).toBeGreaterThan(0);
      for (const paragraph of caseStudy[key].body) expect(paragraph.trim().length).toBeGreaterThan(15);
    }
  });

  it('gives release actions accessible labels and a URL or an explicit preview state', async () => {
    const { caseStudy } = await import('./caseStudy.zh-CN');
    const { englishSummary } = await import('./summary.en');
    expect(caseStudy.hero.links).toHaveLength(4);
    for (const action of [...caseStudy.hero.links, ...englishSummary.links]) {
      expect(action.label.trim()).not.toBe('');
      expect(action.accessibleLabel.trim()).not.toBe('');
      if (action.target.kind === 'available') {
        expect(action.target.url).toMatch(/^(https?:\/\/[^\s]+|#[a-z][a-z-]*)$/);
      } else {
        expect(action.target.url).toBeNull();
        expect(action.target.previewLabel).toBe('即将开放');
      }
    }
  });

  it('keeps the English summary concise and describes the showcase scope', async () => {
    const { englishSummary } = await import('./summary.en');
    expect(englishSummary.title.length).toBeGreaterThan(3);
    expect(englishSummary.summary.length).toBeGreaterThan(30);
    expect(englishSummary.role).toMatch(/showcase/i);
    expect(englishSummary.capabilities.length).toBeGreaterThan(2);
    expect(strings(englishSummary).join(' ').split(/\s+/).length).toBeLessThan(260);
  });

  it('keeps all content and the real rendered page within the public language policy', async () => {
    const { caseStudy } = await import('./caseStudy.zh-CN');
    const { englishSummary } = await import('./summary.en');
    const { default: App } = await import('../App');
    for (const value of strings([caseStudy, englishSummary])) {
      expect(value.trim(), 'Empty content string').not.toBe('');
      expect(violatesPolicy(value), `Policy violation in public content: ${value}`).toBe(false);
    }
    expect(violatesPolicy(renderToStaticMarkup(createElement(App)))).toBe(false);
  });

  it.each([
    '/capture/' + 'ws' + '-78.png', 'https://example.com/' + 'pull/' + '43',
    'p' + 'r #43', 'j' + 'ira', 'te' + 'am project', 'te' + 'am members', '团队项目',
    '增长 30%', 'accuracy 98.5 percent', '提升百分之三十', '全部由我独立开发',
    '/capture/%77%73-78.png', 'T' + 'BD',
  ])('rejects restricted metadata and unsupported claims: %s', (value) => {
    expect(violatesPolicy(value)).toBe(true);
  });

  it('detects configured identities case-insensitively in prose and URL paths', () => {
    const fixtureNames = ['Example Reviewer'];
    expect(violatesPolicy('example reviewer authored this', fixtureNames)).toBe(true);
    expect(violatesPolicy('/people/EXAMPLE%20REVIEWER', fixtureNames)).toBe(true);
    expect(violatesPolicy('An Example Reviewership', fixtureNames)).toBe(false);
    expect(violatesPolicy('Zhan Jin · Grainjin0206')).toBe(false);
  });

  it('does not mistake product and dependency terminology for restricted metadata', () => {
    expect(violatesPolicy('Provider operations, membership, WebSocket, ws-8.18.0 and 60–90 秒录屏')).toBe(false);
  });
});
