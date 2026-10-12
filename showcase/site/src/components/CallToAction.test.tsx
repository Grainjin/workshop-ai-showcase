import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CallToAction } from './CallToAction';
import { createReleaseLinks } from '../content/release-links';

describe('usable release fallbacks', () => {
  it('keeps unavailable Demo/source at experience guidance and video at product captures', () => {
    const [demo, video, github] = createReleaseLinks({});
    expect(renderToStaticMarkup(<CallToAction action={demo} />)).toContain('href="#experience"');
    expect(renderToStaticMarkup(<CallToAction action={video} />)).toContain('href="#walkthrough"');
    expect(renderToStaticMarkup(<CallToAction action={github} />)).toContain('href="#experience"');
    expect(renderToStaticMarkup(<CallToAction action={video} language="en" />)).toContain('In preparation');
  });

  it('preserves every configured external destination', () => {
    const actions = createReleaseLinks({ VITE_DEMO_URL: 'https://demo.example.com',
      VITE_VIDEO_URL: 'https://video.example.com', VITE_GITHUB_URL: 'https://github.com/example/project' });
    const html = actions.slice(0, 3).map(action => renderToStaticMarkup(<CallToAction action={action} />));
    expect(html[0]).toContain('href="https://demo.example.com/"');
    expect(html[1]).toContain('href="https://video.example.com/"');
    expect(html[2]).toContain('href="https://github.com/example/project"');
  });
});
