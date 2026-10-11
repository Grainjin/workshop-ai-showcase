import type { CaseStudyContent } from '../content/types';
import NarrativeSection from './NarrativeSection';

export default function Evidence({ content }: { content: CaseStudyContent['evidence'] }) {
  return (
    <NarrativeSection content={content}>
      <div className="evidence-list">{content.records.map((record, index) => <article key={record.title}
        aria-labelledby={`evidence-record-${index}-title`}>
        <h3 id={`evidence-record-${index}-title`}>{record.title}</h3>
        <p><time dateTime={record.date}>{record.date}</time> · <code>{record.sourcePath}</code></p>
        <p>{record.summary}</p><p className="status">{record.limits}</p>
      </article>)}</div>
    </NarrativeSection>
  );
}
