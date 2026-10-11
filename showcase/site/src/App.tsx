import { caseStudy } from './content/caseStudy.zh-CN';
import { englishSummary } from './content/summary.en';
import SiteHeader from './components/SiteHeader';
import Hero from './components/Hero';
import ProblemStatement from './components/ProblemStatement';
import ProductJourney from './components/ProductJourney';
import EnglishSummary from './components/EnglishSummary';
import NarrativeSection, { Details } from './components/NarrativeSection';
import AILayer from './components/AILayer';
import DecisionSupport from './components/DecisionSupport';
import ArchitectureComparison from './components/ArchitectureComparison';
import Evidence from './components/Evidence';
import Walkthrough from './components/Walkthrough';

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main-content">{caseStudy.interface.skipLink}</a>
      <SiteHeader sections={caseStudy.interface.navigation} />
      <main id="main-content" className="content-shell" tabIndex={-1}>
        <Hero content={caseStudy.hero} />
        <ProblemStatement content={caseStudy.problem} />
        <ProductJourney content={caseStudy.journey} />
        <Walkthrough content={caseStudy.walkthrough} />
        <AILayer content={caseStudy.aiLayer} />
        <DecisionSupport content={caseStudy.decisionSupport} />
        <ArchitectureComparison content={caseStudy.architecture} />
        <NarrativeSection content={caseStudy.showcaseEdition}><Details items={caseStudy.showcaseEdition.changes} /></NarrativeSection>
        <Evidence content={caseStudy.evidence} />
        <NarrativeSection content={caseStudy.limitations}><Details items={caseStudy.limitations.items} /></NarrativeSection>
        <NarrativeSection content={caseStudy.reflection}><Details items={caseStudy.reflection.nextSteps} /></NarrativeSection>
        <section id={caseStudy.releaseStatus.id} tabIndex={-1} aria-labelledby="release-status-title">
          <h2 id="release-status-title">{caseStudy.releaseStatus.title}</h2>
          {caseStudy.releaseStatus.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
          <Details items={caseStudy.releaseStatus.items} />
        </section>
        <EnglishSummary content={englishSummary} />
      </main>
      <footer className="content-shell">
        <p>{caseStudy.interface.footer}</p>
        <address className="footer-contact">
          {caseStudy.interface.contact.name} ·{' '}
          <a href={`tel:${caseStudy.interface.contact.phone}`}>{caseStudy.interface.contact.phone}</a> ·{' '}
          <a href={`mailto:${caseStudy.interface.contact.email}`}>{caseStudy.interface.contact.email}</a>
        </address>
      </footer>
    </>
  );
}
