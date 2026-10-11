import { createEnglishSummary } from './content/summary.en';
import type { ReleaseEnvironment } from './content/types';

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);

export function createNoscriptSummary(env: ReleaseEnvironment): string {
  const content = createEnglishSummary(env);
  const paragraphs = [content.summary, content.role, content.architecture, content.limitations];
  const links = content.links.map((link) => link.target.kind === 'available'
    ? `<li><a href="${escapeHtml(link.target.url)}" aria-label="${escapeHtml(`${link.label} · ${link.accessibleLabel}`)}">${escapeHtml(link.label)}</a></li>`
    : `<li>${escapeHtml(link.label)} — In preparation</li>`).join('');
  return `<noscript><main class="content-shell" lang="en" aria-labelledby="offline-summary-title">
    <section><h1 id="offline-summary-title">${escapeHtml(content.title)}</h1>
    ${paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
    <ul>${content.capabilities.map((capability) => `<li>${escapeHtml(capability)}</li>`).join('')}</ul>
    <ul>${links}</ul></section></main></noscript>`;
}
