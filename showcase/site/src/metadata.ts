import { readPublicUrl } from './content/release-links';
import type { ReleaseEnvironment } from './content/types';

const title = 'Workshop AI｜AI 本地服务交易平台';
const description = '中文产品案例：从服务发现、报价比较到预约履约，解析 AI 助手、历史报价决策支持、演示架构与验证边界。';
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
