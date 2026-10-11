import type { EnglishSummaryContent, ReleaseEnvironment } from './types';
import { createReleaseLinks } from './release-links';

const summaryContent = {
  language: 'en', id: 'english-summary', title: 'Workshop AI — project summary',
  summary: 'A local-services marketplace connecting discovery, comparison, booking, quotes, payment, fulfilment and reviews. AI helps interpret needs and reviews; business changes require explicit confirmation.',
  role: 'Personal showcase maintenance: product synthesis, baseline fixes, demo safeguards and release preparation.',
  capabilities: ['Location and service filters, favourites and historical quote references.',
    'Tool Calling, recommendations, review summaries and confirmation cards.',
    'Customer, Provider and Admin demo roles with simulated payments.'],
  architecture: 'The full local stack retains vector retrieval and background tasks. The planned lightweight public stack uses FastAPI, PostgreSQL and server-side LLM calls with database review context.',
  limitations: 'Fictional data and simulated transactions. Local verification does not establish live deployment, vendor availability or operational impact. Public URLs and the walkthrough are being prepared.',
  returnLabel: 'Back to the Chinese overview',
} as const;

export function createEnglishSummary(env: ReleaseEnvironment): EnglishSummaryContent {
  return {
    ...summaryContent,
    links: createReleaseLinks(env).filter((link) => link.id !== 'english-summary').map((link) => ({
      ...link,
      label: { demo: 'Live demo', video: 'Product walkthrough', github: 'Source code', 'english-summary': 'English summary' }[link.id],
      accessibleLabel: { demo: 'Open the Workshop AI live demo', video: 'Watch the Workshop AI product walkthrough',
        github: 'View the Workshop AI showcase source code', 'english-summary': 'Read the English summary' }[link.id],
    })),
  };
}

export const englishSummary = createEnglishSummary(import.meta.env ?? {});
