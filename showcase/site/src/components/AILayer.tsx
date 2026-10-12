import type { CaseStudyContent } from '../content/types';
import NarrativeSection, { Details } from './NarrativeSection';
import DiagramFigure from './DiagramFigure';
import { ProductCapture } from './Walkthrough';

export default function AILayer({ content }: { content: CaseStudyContent['aiLayer'] }) {
  return (
    <NarrativeSection content={content}>
      <Details items={content.capabilities} />
      <div className="confirmation-layout">
        <DiagramFigure content={content.diagram} />
        <ol className="confirmation-steps" aria-label={content.diagram.textLabel}>
          {content.confirmationSteps.map((step) => <li key={step.title}>
            <h3>{step.title}</h3><p>{step.body}</p>
          </li>)}
        </ol>
      </div>
      <div className="ai-capture"><ProductCapture capture={content.capture} /></div>
    </NarrativeSection>
  );
}
