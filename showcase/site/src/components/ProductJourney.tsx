import type { CaseStudyContent } from '../content/types';
import NarrativeSection from './NarrativeSection';

export default function ProductJourney({ content }: { content: CaseStudyContent['journey'] }) {
  return (
    <NarrativeSection content={content}>
      <ol className="journey-list">
        {content.steps.map((step) => <li key={step.title}>
          <h3>{step.title}</h3><p>{step.body}</p>
        </li>)}
      </ol>
    </NarrativeSection>
  );
}
