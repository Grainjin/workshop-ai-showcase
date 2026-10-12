export type SectionId = 'overview' | 'problem' | 'journey' | 'walkthrough' | 'ai' | 'decisions' |
  'architecture' | 'process' | 'evidence' | 'limitations' | 'reflection';

export interface ContentSection {
  readonly id: SectionId;
  readonly title: string;
  readonly body: readonly string[];
}

export interface ContentDetail {
  readonly title: string;
  readonly body: string;
}

export interface DiagramContent {
  readonly src: string;
  readonly title: string;
  readonly description: string;
  readonly textLabel: string;
}

export type LinkTarget =
  | { readonly kind: 'available'; readonly url: string }
  | { readonly kind: 'coming-soon'; readonly url: null; readonly previewLabel: '即将开放' };

export interface CallToActionContent {
  readonly id: 'demo' | 'video' | 'github' | 'english-summary';
  readonly label: string;
  readonly accessibleLabel: string;
  readonly target: LinkTarget;
}

export interface ArchitectureMode {
  readonly id: 'local' | 'public';
  readonly title: string;
  readonly body: string;
  readonly status: string;
  readonly components: readonly string[];
  readonly diagram: DiagramContent;
  readonly connections: readonly ContentDetail[];
}

export interface EvidenceRecord {
  readonly title: string;
  readonly date: `${number}-${number}-${number}`;
  readonly sourcePath: string;
  readonly summary: string;
  readonly limits: string;
}

export interface WalkthroughCapture {
  readonly src: string;
  readonly alt: string;
  readonly title: string;
  readonly description: string;
  readonly date: `${number}-${number}-${number}`;
  readonly sourcePath: string;
  readonly limitation: string;
  readonly width: number;
  readonly height: number;
}

export interface CaseStudyContent {
  readonly language: 'zh-CN';
  readonly hero: ContentSection & {
    readonly eyebrow: string;
    readonly subtitle: string;
    readonly status: string;
    readonly links: readonly CallToActionContent[];
  };
  readonly problem: ContentSection & { readonly tensions: readonly ContentDetail[] };
  readonly journey: ContentSection & { readonly steps: readonly ContentDetail[] };
  readonly walkthrough: ContentSection & {
    readonly videoStatus: ContentDetail & { readonly linkLabel: string | null };
    readonly videoAction: CallToActionContent;
    readonly demoAction: CallToActionContent;
    readonly demoFallbackLabel: string;
    readonly captures: readonly WalkthroughCapture[];
  };
  readonly aiLayer: ContentSection & {
    readonly capabilities: readonly ContentDetail[];
    readonly diagram: DiagramContent;
    readonly confirmationSteps: readonly ContentDetail[];
    readonly capture: WalkthroughCapture;
  };
  readonly decisionSupport: ContentSection & { readonly mechanisms: readonly ContentDetail[] };
  readonly architecture: ContentSection & { readonly modes: readonly ArchitectureMode[] };
  readonly showcaseEdition: ContentSection & { readonly changes: readonly ContentDetail[] };
  readonly evidence: ContentSection & { readonly records: readonly EvidenceRecord[] };
  readonly limitations: ContentSection & { readonly items: readonly ContentDetail[] };
  readonly reflection: ContentSection & { readonly nextSteps: readonly ContentDetail[] };
  readonly releaseStatus: {
    readonly id: 'experience'; readonly title: string;
    readonly body: readonly string[]; readonly items: readonly ContentDetail[];
  };
  readonly interface: {
    readonly skipLink: string; readonly footer: string;
    readonly contact: { readonly name: string; readonly phone: string; readonly email: string };
    readonly navigation: readonly { readonly id: SectionId; readonly label: string }[];
  };
}

export interface EnglishSummaryContent {
  readonly language: 'en';
  readonly id: 'english-summary';
  readonly title: string;
  readonly summary: string;
  readonly role: string;
  readonly capabilities: readonly string[];
  readonly architecture: string;
  readonly limitations: string;
  readonly returnLabel: string;
  readonly links: readonly CallToActionContent[];
}

export interface ReleaseEnvironment {
  readonly VITE_CANONICAL_URL?: string;
  readonly VITE_DEMO_URL?: string;
  readonly VITE_VIDEO_URL?: string;
  readonly VITE_GITHUB_URL?: string;
}
