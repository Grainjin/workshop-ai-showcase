import { readPublicUrl } from './content/release-links';
import type { ReleaseEnvironment } from './content/types';

const title = 'Workshop AI｜AI 辅助的本地服务平台 · 产品设计与实现';
const description = 'Zhan Jin 的中文产品介绍：理解本地服务需求、双角色交易流程、分阶段报价与 AI 用户确认机制，以及设计落地、客户验收和后续市场测试。';
const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);

export function createMetadataTags(env: ReleaseEnvironment): string {
  const canonical = readPublicUrl(env.VITE_CANONICAL_URL, 'VITE_CANONICAL_URL');
  const image = canonical ? new URL('/social-preview.png', canonical).href : '/social-preview.png';
  return [
    `<meta name="description" content="${escapeHtml(description)}" />`,
    '<meta property="og:type" content="website" />',
    '<meta property="og:locale" content="zh_CN" />',
    `<meta property="og:title" content="${escapeHtml(title)}" />`,
    `<meta property="og:description" content="${escapeHtml(description)}" />`,
    `<meta property="og:image" content="${escapeHtml(image)}" />`,
    '<meta property="og:image:alt" content="Workshop AI：从服务发现到预约履约的 AI 产品案例" />',
    '<meta name="twitter:card" content="summary_large_image" />',
    ...(canonical ? [`<link rel="canonical" href="${escapeHtml(canonical)}" />`,
      `<meta property="og:url" content="${escapeHtml(canonical)}" />`] : []),
  ].join('\n    ');
}
