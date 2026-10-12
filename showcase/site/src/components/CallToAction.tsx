import type { CallToActionContent } from '../content/types';

export function CallToAction({ action, language = 'zh-CN' }: {
  action: CallToActionContent; language?: 'zh-CN' | 'en';
}) {
  const available = action.target.kind === 'available';
  const status = language === 'en'
    ? available ? 'Available' : 'In preparation'
    : available ? action.id === 'english-summary' ? '可阅读' : '可访问' : '即将开放';
  const fallback = action.id === 'video' ? '#walkthrough' : '#experience';
  return (
    <a className="action-link" href={available ? action.target.url! : fallback}
      aria-label={`${action.label} · ${action.accessibleLabel} · ${status}`}>
      <span>{action.label}</span><span className="action-status">{status}</span>
    </a>
  );
}

export default function CallToActions({ actions, language = 'zh-CN' }: {
  actions: readonly CallToActionContent[]; language?: 'zh-CN' | 'en';
}) {
  return (
    <nav className="action-list" aria-label={language === 'en' ? 'Project links' : '产品入口'}>
      {actions.map((action) => <CallToAction key={action.id} action={action} language={language} />)}
    </nav>
  );
}
