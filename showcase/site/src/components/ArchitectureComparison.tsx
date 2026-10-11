import type { CaseStudyContent } from '../content/types';
import NarrativeSection, { Details } from './NarrativeSection';
import DiagramFigure from './DiagramFigure';

export default function ArchitectureComparison({ content }: { content: CaseStudyContent['architecture'] }) {
  return (
    <NarrativeSection content={content}>
      <div className="architecture-modes">
        {content.modes.map((mode) => <article key={mode.id} id={`architecture-${mode.id}`}
          aria-labelledby={`architecture-${mode.id}-title`}>
          <h3 id={`architecture-${mode.id}-title`}>{mode.title}</h3>
          <p className="status">{mode.status}</p><p>{mode.body}</p>
          <DiagramFigure content={mode.diagram} />
          <div role="group" aria-label={mode.diagram.textLabel}>
            <h4>{mode.diagram.textLabel}</h4>
            <Details items={mode.connections} />
            <ul>{mode.components.map((component) => <li key={component}>{component}</li>)}</ul>
          </div>
        </article>)}
      </div>
    </NarrativeSection>
  );
}
