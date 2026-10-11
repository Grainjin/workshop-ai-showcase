import { describe, expect, it, vi, afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import App from './App';

const render = () => renderToStaticMarkup(<App />);
const section = (html: string, id: string) => html.match(new RegExp(`<section[^>]*id="${id}"[\\s\\S]*?</section>`))?.[0] ?? '';

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe('60-second recruiter path', () => {
  it('introduces the product and its actual public-showcase status before the product journey', () => {
    const html = render();
    expect(html).toContain('<header');
    expect(html).toContain('Workshop AI｜AI 本地服务交易平台');
    expect(html).toContain('从服务发现、智能决策到预约履约的一体化 Marketplace 产品');
    expect(section(html, 'overview')).toContain('公开部署和产品录屏仍在准备中');
    expect(html.indexOf('id="overview"')).toBeLessThan(html.indexOf('id="journey"'));
  });

  it('provides four focusable primary actions with explicit availability and useful destinations', () => {
    const html = render();
    const actions = html.match(/<nav[^>]*aria-label="产品入口"[\s\S]*?<\/nav>/)?.[0] ?? '';
    expect(actions.match(/<a /g)).toHaveLength(4);
    for (const label of ['在线体验', '观看 Demo', '查看 GitHub', 'English Summary']) expect(actions).toContain(label);
    expect(actions.match(/>即将开放<\/span>/g)).toHaveLength(3);
    expect(actions).toContain('可阅读');
    expect(actions).not.toMatch(/href="(?:|#)"|aria-disabled|tabindex="-1"/);
    for (const [, id] of actions.matchAll(/href="#([^"]+)"/g)) {
      expect(html).toMatch(new RegExp(`id="${id}"[^>]*tabindex="-1"`));
    }
    expect(section(html, 'release-status')).toContain('发布入口配置前显示即将开放');
  });

  it('renders the eight transaction steps in their actual order with explanatory text', () => {
    const journey = section(render(), 'journey');
    const headings = Array.from(journey.matchAll(/<h3[^>]*>(.*?)<\/h3>/g), (match) => match[1]);
    expect(headings).toEqual(['发现', '比较', '收藏', '预约', '报价', '支付', '履约', '评价']);
    expect(journey).toContain('<ol');
    expect(journey).toContain('不产生真实扣款');
  });

  it('retains the visible action label in each accessible name', () => {
    const html = render();
    for (const label of ['在线体验', '观看 Demo', '查看 GitHub', 'English Summary', 'Live demo', 'Product walkthrough', 'Source code']) {
      expect(html).toContain(`aria-label="${label} · `);
    }
  });

  it('keeps all required destinations substantive and keyboard focusable', () => {
    const html = render();
    for (const id of ['overview', 'journey', 'ai', 'decisions', 'architecture', 'evidence', 'reflection']) {
      const body = section(html, id);
      expect(body).toContain('tabindex="-1"');
      expect(body).toMatch(/<p[^>]*>[^<]{20,}<\/p>/);
    }
    expect(html).toContain('href="#main-content"');
    expect(html).toMatch(/<main id="main-content"[^>]*tabindex="-1"/);
  });

  it('exposes a complete non-modal English summary with a return path', () => {
    const summary = section(render(), 'english-summary');
    expect(summary).toContain('lang="en"');
    expect(summary).toContain('aria-labelledby="english-summary-title"');
    expect(summary).toContain('Personal showcase maintenance');
    expect(summary).toContain('Tool Calling');
    expect(summary).toContain('FastAPI, PostgreSQL');
    expect(summary).toContain('Fictional data and simulated transactions');
    expect(summary).toContain('href="#overview"');
    expect(summary).not.toContain('role="dialog"');
  });

  it('renders the typed comparison, architecture, evidence and limitation details for scrutiny', () => {
    const html = render();
    expect(section(html, 'problem')).toContain('信任判断');
    expect(section(html, 'ai')).toContain('可理解的降级');
    expect(section(html, 'decisions')).toContain('历史报价决策支持');
    expect(section(html, 'architecture')).toContain('Milvus');
    expect(section(html, 'architecture')).toContain('Demo Payment Adapter');
    expect(section(html, 'evidence')).toContain('2026-10-10');
    expect(section(html, 'evidence')).toContain('历史截图不是当前浏览器端到端验收');
    expect(section(html, 'limitations')).toContain('Demo 支付不会扣款');
    expect(section(html, 'reflection')).toContain('推荐依据、确认卡理解和报价参考');
    const ids = Array.from(html.matchAll(/\bid="([^"]+)"/g), (match) => match[1]);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('uses configured URLs as working available actions instead of preview destinations', async () => {
    vi.stubEnv('VITE_DEMO_URL', 'https://demo.example.com/');
    vi.stubEnv('VITE_VIDEO_URL', 'https://video.example.com/');
    vi.stubEnv('VITE_GITHUB_URL', 'https://github.com/example/showcase');
    vi.resetModules();
    const { default: ConfiguredApp } = await import('./App');
    const html = renderToStaticMarkup(<ConfiguredApp />);
    const actions = html.match(/<nav[^>]*aria-label="产品入口"[\s\S]*?<\/nav>/)?.[0] ?? '';
    for (const url of ['https://demo.example.com/', 'https://video.example.com/', 'https://github.com/example/showcase']) {
      expect(actions).toContain(`href="${url}"`);
    }
    expect(actions.match(/>可访问<\/span>/g)).toHaveLength(3);
    expect(actions).not.toContain('即将开放');
  });

  it.each([
    [false, false, false],
    [true, false, false],
    [false, true, false],
    [false, false, true],
    [true, true, false],
    [true, false, true],
    [false, true, true],
    [true, true, true],
  ])('keeps per-link release explanations aligned with demo=%s, video=%s, source=%s availability', async (demo, video, github) => {
    vi.stubEnv('VITE_DEMO_URL', demo ? 'https://demo.example.com/' : '');
    vi.stubEnv('VITE_VIDEO_URL', video ? 'https://video.example.com/' : '');
    vi.stubEnv('VITE_GITHUB_URL', github ? 'https://github.com/example/showcase' : '');
    vi.resetModules();
    const { default: ConfiguredApp } = await import('./App');
    const html = renderToStaticMarkup(<ConfiguredApp />);
    const status = section(html, 'release-status');
    const checks = [
      { label: '在线体验', available: demo, preparation: '公开部署、角色登录与浏览器路径仍需上线验收' },
      { label: '观看 Demo', available: video, preparation: '带字幕的产品录屏仍在准备' },
      { label: '查看 GitHub', available: github, preparation: '公开源码链接尚未配置' },
    ];
    for (const check of checks) {
      const message = status.match(new RegExp(`<dt>${check.label}</dt><dd>([^<]+)</dd>`))?.[1] ?? '';
      if (check.available) {
        expect(message).toContain('入口已配置');
        expect(message).not.toContain(check.preparation);
      } else {
        expect(message).toContain(check.preparation);
        expect(message).not.toContain('入口已配置');
      }
    }
    if (demo || video || github) expect(status).not.toContain('在线体验、产品录屏和公开源码入口仍在准备');
    if (demo && video && github) {
      expect(status).not.toMatch(/仍在准备|尚未配置|仍需上线验收/);
    }
  });
});

describe('AI and architecture presentation', () => {
  // Missing diagrams, a leaked full-stack dependency, or a reordered confirmation gate
  // would misrepresent the runtime and the user's control over mutations.
  it('separates the full and lightweight architectures with accessible diagrams and text companions', () => {
    const architecture = section(render(), 'architecture');
    const local = architecture.match(/<article[^>]*id="architecture-local"[\s\S]*?<\/article>/)?.[0] ?? '';
    const publicMode = architecture.match(/<article[^>]*id="architecture-public"[\s\S]*?<\/article>/)?.[0] ?? '';
    expect(local).toContain('aria-labelledby="architecture-local-title"');
    expect(local).toMatch(/<img[^>]*src="[^"]*local-full-stack.svg[^>]*alt="完整本地模式架构图"/);
    for (const component of ['Milvus', 'TEI', 'Redis', 'Celery']) expect(local).toContain(component);
    expect(local).toContain('文字说明');
    expect(publicMode).toContain('aria-labelledby="architecture-public-title"');
    expect(publicMode).toMatch(/<img[^>]*src="[^"]*public-demo-stack.svg[^>]*alt="轻量公开模式架构图"/);
    expect(publicMode).toContain('PostgreSQL 数据库评价上下文');
    expect(publicMode).not.toMatch(/Milvus|TEI|Redis|Celery|向量|Embedding/i);
    expect(publicMode).toContain('线上部署待完成');
  });

  it.each([
    ['local-full-stack.svg', ['Milvus', 'TEI', 'Redis', 'Celery']],
    ['public-demo-stack.svg', ['PostgreSQL', '数据库评价上下文', 'Demo Payment Adapter']],
    ['ai-confirmation-flow.svg', ['Tool Calling', '确认卡', '用户确认', '执行']],
  ] as const)('ships a self-described local diagram: %s', (filename, labels) => {
    const path = resolve('../assets/diagrams', filename);
    expect(existsSync(path), 'The rendered diagram must resolve to a shipped local asset').toBe(true);
    const svg = readFileSync(path, 'utf8');
    expect(svg).toMatch(/<svg[^>]*role="img"[^>]*aria-labelledby="[^"]+"/);
    expect(svg).toMatch(/<title id="[^"]+">[^<]+<\/title>/);
    expect(svg).toMatch(/<desc id="[^"]+">[^<]+<\/desc>/);
    for (const label of labels) expect(svg).toContain(label);
    if (filename === 'public-demo-stack.svg') expect(svg).not.toMatch(/Milvus|TEI|Redis|Celery|向量|Embedding/i);
  });

  it('makes confirmation-before-mutation readable in order and explains review-summary fallback', () => {
    const ai = section(render(), 'ai');
    expect(ai).toMatch(/<img[^>]*src="[^"]*ai-confirmation-flow.svg[^>]*alt="AI 操作确认流程图"/);
    const flow = ai.match(/<ol[^>]*aria-label="AI 操作确认流程文字说明"[\s\S]*?<\/ol>/)?.[0] ?? '';
    const headings = Array.from(flow.matchAll(/<h3[^>]*>(.*?)<\/h3>/g), (match) => match[1]);
    expect(headings).toEqual(['理解需求', 'Tool Calling', '生成确认卡', '用户确认', '执行与反馈']);
    expect(flow).toContain('确认前不改变业务状态');
    expect(flow).toContain('未确认时不执行');
    expect(ai).toContain('PostgreSQL 数据库评价上下文');
    expect(ai).toContain('规则回退');
    expect(ai).toContain('原始评价');
  });

  it('labels historical quote support as rules and preserves concrete selection mechanisms', () => {
    const decisions = section(render(), 'decisions');
    expect(decisions).toContain('基于规则的历史决策支持');
    expect(decisions).toContain('不预测未来价格');
    expect(decisions).toContain('样本不足');
    expect(decisions).toContain('位置级联');
    expect(decisions).toContain('搜索筛选');
    expect(decisions).toContain('收藏');
  });

  it('pairs verified engineering records with dates, sources and limits instead of implying hosted acceptance', () => {
    const evidence = section(render(), 'evidence');
    expect(evidence).toContain('401');
    expect(evidence).toContain('58');
    expect(evidence).toContain('历史基线');
    expect(evidence).toContain('托管 CI 尚未运行');
    expect(evidence).toContain('公开部署与浏览器路径仍需验收');
    const records = [...evidence.matchAll(/<article[^>]*[\s\S]*?<\/article>/g)].map((match) => match[0]);
    expect(records.length).toBeGreaterThanOrEqual(3);
    for (const record of records) {
      expect(record).toMatch(/<time date[Tt]ime="2026-10-10">/);
      expect(record).toContain('docs/release/foundation-verification.md');
      expect(record).toMatch(/<p class="status">[^<]+<\/p>/);
    }
  });
});

describe('verified product walkthrough', () => {
  // Removing provenance, implying that a blocked recapture is current, or silently
  // substituting a fabricated video would turn historical evidence into a false claim.
  it('presents the verified historical search captures as a labelled static gallery', () => {
    const walkthrough = section(render(), 'walkthrough');
    const figures = [...walkthrough.matchAll(/<figure[^>]*>[\s\S]*?<\/figure>/g)].map((match) => match[0]);

    expect(walkthrough).toContain('当前可核对材料');
    expect(figures).toHaveLength(2);
    expect(figures[0]).toMatch(/<img[^>]*src="[^"]*provider-search-results\.png[^>]*alt="服务商搜索结果页的历史验证截图"/);
    expect(figures[0]).toContain('候选服务商卡片与结果信息');
    expect(figures[0]).not.toContain('收藏入口');
    expect(figures[1]).toMatch(/<img[^>]*src="[^"]*provider-search-filters-expanded\.png[^>]*alt="服务商筛选面板展开状态的历史验证截图"/);
    for (const figure of figures) {
      expect(figure).toContain('历史验证截图');
      expect(figure).toContain('2026-10-10');
      expect(figure).toContain('不是当前浏览器端到端验收');
      expect(figure).toMatch(/<img[^>]*loading="lazy"[^>]*width="1470"[^>]*height="727"/);
    }
  });

  it('states why fresh media stopped and leaves video as preparation instead of fake playback', () => {
    const walkthrough = section(render(), 'walkthrough');
    const steps = Array.from(walkthrough.matchAll(/<dt>(.*?)<\/dt>/g), (match) => match[1]);

    expect(walkthrough).toContain('2026-10-12');
    expect(walkthrough).toContain('一键 Customer 登录');
    expect(walkthrough).toContain('位置级联');
    expect(walkthrough).toContain('未继续制作新的截图或视频');
    expect(walkthrough).toContain('60–90 秒录屏准备中');
    expect(walkthrough).toContain('不产生真实扣款');
    expect(walkthrough).toContain('href="#release-status"');
    expect(walkthrough).toContain('查看 Live Demo 准备状态');
    expect(steps).toEqual(expect.arrayContaining(['登录与发现', '筛选与收藏', '预约与参考价', 'AI 确认卡', '模拟支付说明']));
    expect(walkthrough).not.toContain('<video');
    expect(walkthrough).not.toMatch(/\.mp4/);
  });

  it('uses configured video and demo links consistently across hero, walkthrough and release status', async () => {
    vi.stubEnv('VITE_DEMO_URL', 'https://demo.example.com/');
    vi.stubEnv('VITE_VIDEO_URL', 'https://video.example.com/');
    vi.resetModules();
    const { default: ConfiguredApp } = await import('./App');
    const html = renderToStaticMarkup(<ConfiguredApp />);
    const hero = section(html, 'overview');
    const walkthrough = section(html, 'walkthrough');
    const releaseStatus = section(html, 'release-status');

    expect(hero).toContain('在线体验与产品录屏入口已配置');
    expect(hero).not.toContain('公开部署和产品录屏仍在准备');
    expect(walkthrough).toContain('产品录屏入口已配置');
    expect(walkthrough).toContain('href="https://video.example.com/"');
    expect(walkthrough).toContain('观看已配置产品录屏');
    expect(walkthrough).toContain('href="https://demo.example.com/"');
    expect(walkthrough).toContain('打开 Live Demo');
    expect(walkthrough).not.toMatch(/录屏准备中|暂不提供播放器|海报或字幕文件/);
    expect(releaseStatus).toContain('产品录屏入口已配置');
    expect(releaseStatus).not.toContain('带字幕的产品录屏仍在准备');
  });
});
