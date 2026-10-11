import type { CaseStudyContent } from '../content/types';

export default function SiteHeader({ sections }: { sections: CaseStudyContent['interface']['navigation'] }) {
  return (
    <header className="site-header content-shell">
      <a className="site-brand" href="#overview">Workshop AI</a>
      <nav aria-label="案例章节">
        <ul className="section-links">
          {sections.map((section) => <li key={section.id}>
            <a href={`#${section.id}`}>{section.label}</a>
          </li>)}
          <li><a href="#english-summary" lang="en">English Summary</a></li>
        </ul>
      </nav>
    </header>
  );
}
