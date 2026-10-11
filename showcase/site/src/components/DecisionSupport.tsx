import type { CaseStudyContent } from '../content/types';
import NarrativeSection, { Details } from './NarrativeSection';

export default function DecisionSupport({ content }: { content: CaseStudyContent['decisionSupport'] }) {
  return <NarrativeSection content={content}><Details items={content.mechanisms} /></NarrativeSection>;
}
