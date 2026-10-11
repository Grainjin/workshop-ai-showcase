import type { CallToActionContent, LinkTarget, ReleaseEnvironment } from './types';

export function readPublicUrl(value: string | undefined, variableName: string): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error();
    return url.href;
  } catch {
    throw new Error(`${variableName} must be an absolute HTTP(S) URL without credentials`);
  }
}

function releaseTarget(value: string | undefined, name: string): LinkTarget {
  const url = readPublicUrl(value, name);
  return url ? { kind: 'available', url } : { kind: 'coming-soon', url: null, previewLabel: '即将开放' };
}

export function createReleaseLinks(env: ReleaseEnvironment): readonly CallToActionContent[] {
  return [
    { id: 'demo', label: '在线体验', accessibleLabel: '在线体验 Workshop AI 演示产品',
      target: releaseTarget(env.VITE_DEMO_URL, 'VITE_DEMO_URL') },
    { id: 'video', label: '观看 Demo', accessibleLabel: '观看 Workshop AI 产品流程录屏',
      target: releaseTarget(env.VITE_VIDEO_URL, 'VITE_VIDEO_URL') },
    { id: 'github', label: '查看 GitHub', accessibleLabel: '查看 Workshop AI 展示版源码与运行说明',
      target: releaseTarget(env.VITE_GITHUB_URL, 'VITE_GITHUB_URL') },
    { id: 'english-summary', label: 'English Summary', accessibleLabel: 'Read the concise English project summary',
      target: { kind: 'available', url: '#english-summary' } },
  ];
}
