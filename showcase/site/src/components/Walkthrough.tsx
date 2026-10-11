import type { CaseStudyContent } from '../content/types';
import NarrativeSection, { Details } from './NarrativeSection';

export default function Walkthrough({ content }: { content: CaseStudyContent['walkthrough'] }) {
  return (
    <NarrativeSection content={content}>
      <div className="walkthrough-status" aria-label="产品实录准备状态">
        <article>
          <h3>{content.verification.title}</h3>
          <p>{content.verification.body}</p>
        </article>
        <article>
          <h3>{content.videoStatus.title}</h3>
          <p>{content.videoStatus.body}</p>
          <div className="walkthrough-links">
            {content.videoAction.target.kind === 'available' && content.videoStatus.linkLabel
              ? <a href={content.videoAction.target.url}>{content.videoStatus.linkLabel}</a>
              : null}
            <a href={content.demoAction.target.kind === 'available'
              ? content.demoAction.target.url
              : '#release-status'}>{content.demoFallbackLabel}</a>
          </div>
        </article>
      </div>

      <h3 className="walkthrough-subtitle">固定录屏脚本</h3>
      <Details items={content.steps} />

      <div className="walkthrough-gallery" aria-label="已验证产品截图">
        {content.captures.map((capture) => (
          <figure key={capture.src}>
            <img
              src={capture.src}
              alt={capture.alt}
              loading="lazy"
              width="1470"
              height="727"
            />
            <figcaption>
              <strong>{capture.title}</strong>
              <span>{capture.description}</span>
              <span><time dateTime={capture.date}>{capture.date}</time> · <code>{capture.sourcePath}</code></span>
              <span className="status">{capture.limitation}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </NarrativeSection>
  );
}
