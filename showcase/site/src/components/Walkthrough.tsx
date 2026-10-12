import type { CaseStudyContent, WalkthroughCapture } from '../content/types';
import NarrativeSection from './NarrativeSection';

export function ProductCapture({ capture }: { capture: WalkthroughCapture }) {
  return <figure className="product-capture">
    <img src={capture.src} alt={capture.alt} loading="lazy" width={capture.width} height={capture.height} />
    <figcaption><strong>{capture.title}</strong><span>{capture.description}</span>
      <span className="status">{capture.limitation}</span>
    </figcaption>
  </figure>;
}

export default function Walkthrough({ content }: { content: CaseStudyContent['walkthrough'] }) {
  return <NarrativeSection content={content}>
    <div className="walkthrough-gallery" aria-label="真实产品截图">
      {content.captures.map(capture => <ProductCapture key={capture.src} capture={capture} />)}
    </div>
    <div className="media-guidance">
      <h3>{content.videoStatus.title}</h3><p>{content.videoStatus.body}</p>
      <div className="walkthrough-links">
        {content.videoAction.target.kind === 'available' && content.videoStatus.linkLabel
          ? <a href={content.videoAction.target.url}>{content.videoStatus.linkLabel}</a> : null}
        <a href={content.demoAction.target.kind === 'available' ? content.demoAction.target.url : '#experience'}>
          {content.demoFallbackLabel}
        </a>
      </div>
    </div>
  </NarrativeSection>;
}
