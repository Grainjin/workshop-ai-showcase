import type { EnglishSummaryContent, ReleaseEnvironment } from './types';
import { createReleaseLinks } from './release-links';

const summaryContent = {
  language: 'en', id: 'english-summary', title: 'Workshop AI — product introduction',
  summary: 'An AI-assisted local-services marketplace connecting customers and providers through discovery, requests, phased quotes, payments, fulfilment and aftercare. Page controls and conversation share the same business rules.',
  role: 'This product showcase explains the user journey, product decisions, AI design and implementation. The project received recognition from its University of Sydney project mentor and passed real-client acceptance; market tests in Sydney and Istanbul are forthcoming.',
  capabilities: ['Search, filters, provider details and booking-linked chat.',
    'Separate visit fee, estimated service price and final quote, with customer confirmation at each phase.',
    'Tool Calling and drafts; users confirm consequential actions before backend role and state checks.'],
  architecture: 'Expo and FastAPI connect to PostgreSQL. Current review retrieval uses database context; local vector code remains available but live generative RAG is not verified.',
  limitations: 'Fictional Demo data and simulated payments. The quote capture is preparation, and the AI capture is a local capability explanation without a paid model call. Quantitative impact and cloud acceptance require separate evaluation.',
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
