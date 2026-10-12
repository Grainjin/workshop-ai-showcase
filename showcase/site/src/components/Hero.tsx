import type { CaseStudyContent } from '../content/types';
import CallToActions from './CallToAction';

export default function Hero({ content }: { content: CaseStudyContent['hero'] }) {
  return (
    <section id={content.id} tabIndex={-1} aria-labelledby="case-study-title" className="hero">
      <p className="eyebrow">{content.eyebrow}</p>
      <h1 id="case-study-title">{content.title}</h1>
      <p className="lead">{content.subtitle}</p>
      {content.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
      <p className="status">{content.status}</p>
      <a className="pdf-download" href="/documents/Workshop-AI-Product-Introduction-Zhan-Jin.pdf" download>
        下载完整产品介绍 PDF <span> · Zhan Jin</span>
      </a>
      <CallToActions actions={content.links} />
    </section>
  );
}
