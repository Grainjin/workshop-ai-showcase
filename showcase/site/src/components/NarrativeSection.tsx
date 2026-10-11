import type { ReactNode } from 'react';
import type { ContentDetail, ContentSection } from '../content/types';

export function Details({ items }: { items: readonly ContentDetail[] }) {
  return (
    <dl className="detail-list">
      {items.map((item) => <div key={item.title}>
        <dt>{item.title}</dt><dd>{item.body}</dd>
      </div>)}
    </dl>
  );
}

export default function NarrativeSection({ content, children }: {
  content: ContentSection; children?: ReactNode;
}) {
  return (
    <section id={content.id} tabIndex={-1} aria-labelledby={`${content.id}-title`}>
      <h2 id={`${content.id}-title`}>{content.title}</h2>
      {content.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
      {children}
    </section>
  );
}
