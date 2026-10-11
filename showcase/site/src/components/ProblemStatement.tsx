import type { CaseStudyContent } from '../content/types';
import NarrativeSection, { Details } from './NarrativeSection';

export default function ProblemStatement({ content }: { content: CaseStudyContent['problem'] }) {
  return <NarrativeSection content={content}><Details items={content.tensions} /></NarrativeSection>;
}
