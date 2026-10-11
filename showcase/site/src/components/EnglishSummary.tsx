import type { EnglishSummaryContent } from '../content/types';
import CallToActions from './CallToAction';

export default function EnglishSummary({ content }: { content: EnglishSummaryContent }) {
  return (
    <section id={content.id} tabIndex={-1} lang={content.language} aria-labelledby="english-summary-title">
      <h2 id="english-summary-title">{content.title}</h2>
      <p>{content.summary}</p><p>{content.role}</p>
      <ul className="summary-capabilities">{content.capabilities.map((capability) => <li key={capability}>{capability}</li>)}</ul>
      <p>{content.architecture}</p><p>{content.limitations}</p>
      <CallToActions actions={content.links} language="en" />
      <a className="return-link" href="#overview">{content.returnLabel}</a>
    </section>
  );
}
