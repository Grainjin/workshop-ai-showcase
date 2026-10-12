import { expect, test, type Page } from 'playwright/test';
import { loadViteReleaseEnvironment } from './vite-release-environment';

const releaseTargets = [
  { label: '在线体验', variable: 'VITE_DEMO_URL', fallback: '#experience' },
  { label: '观看 Demo', variable: 'VITE_VIDEO_URL', fallback: '#walkthrough' },
  { label: '查看 GitHub', variable: 'VITE_GITHUB_URL', fallback: '#experience' },
] as const;

const releaseEnvironment = loadViteReleaseEnvironment();
const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  browserErrors.set(page, errors);
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page)).toEqual([]);
});

test('the page fits the viewport and loads without browser errors', async ({ page }, testInfo) => {
  await page.locator('footer').scrollIntoViewIfNeeded();
  await expect(page.locator('.walkthrough-gallery img')).toHaveCount(7);
  await expect.poll(() => page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.documentElement.clientWidth,
  }))).toEqual({ document: 0, body: 0 });
  for (const image of await page.locator('.product-capture img, .diagram-figure img').all()) {
    // Hidden engineering diagrams become visible only when their native details opens.
    if (await image.isVisible()) {
      await image.scrollIntoViewIfNeeded();
      await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
    }
  }
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: testInfo.outputPath('overview.png') });
  await page.screenshot({ path: testInfo.outputPath('whole-page.png'), fullPage: true });
});

test('a self-hosted SC serif font loads for devices without Songti', async ({ page, request }) => {
  const response = await request.get('/fonts/workshop-song-sc-regular.woff2');
  expect(response.status()).toBe(200);
  expect((await response.body()).subarray(0, 4).toString()).toBe('wOF2');
  expect(await page.evaluate(async () => {
    const loaded = await document.fonts.load('17px "Workshop Song SC"', '需求报价确认');
    return loaded.length > 0 && loaded.every(font => font.status === 'loaded');
  })).toBe(true);
});

test('keyboard focus reveals the skip link and reaches main content', async ({ page }) => {
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: '跳至主要内容' });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  expect(await skip.evaluate((element) => parseFloat(getComputedStyle(element).outlineWidth))).toBeGreaterThanOrEqual(3);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main-content$/);
  await expect(page.locator('main#main-content')).toBeFocused();
});

test('section navigation and the English summary have working return paths', async ({ page }) => {
  const navigation = page.getByRole('navigation', { name: '案例章节' });
  const links = await navigation.getByRole('link').all();
  for (const link of links) {
    const target = await link.getAttribute('href');
    expect(target).toMatch(/^#[a-z-]+$/);
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${target}$`));
    await expect(page.locator(target!)).toBeVisible();
  }
  const summary = page.locator('#english-summary');
  await expect(summary.getByRole('heading', { level: 2 })).toBeVisible();
  await expect(summary).toHaveAttribute('lang', 'en');
  await summary.getByRole('link', { name: 'Back to the Chinese overview' }).click();
  await expect(page).toHaveURL(/#overview$/);
});

test('primary actions lead to configured URLs or useful experience guidance', async ({ page }) => {
  const actions = page.getByRole('navigation', { name: '产品入口' });
  for (const { label, variable, fallback } of releaseTargets) {
    const link = actions.getByRole('link', { name: new RegExp(`^${label} ·`) });
    const configured = releaseEnvironment[variable]?.trim();
    if (configured) {
      await expect(link).toHaveAttribute('href', new URL(configured).href);
      await expect(link).toContainText('可访问');
    } else {
      await expect(link).toHaveAttribute('href', fallback);
      await expect(link).toContainText('即将开放');
      await link.click();
      await expect(page).toHaveURL(new RegExp(`${fallback}$`));
      await expect(page.locator(fallback)).toBeVisible();
    }
  }
  await expect(actions.getByRole('link', { name: /^English Summary ·/ })).toHaveAttribute('href', '#english-summary');
});

test('video availability is honest and the static evidence remains usable', async ({ page }) => {
  const walkthrough = page.locator('#walkthrough');
  const configured = releaseEnvironment.VITE_VIDEO_URL?.trim();
  if (configured) {
    await expect(walkthrough.getByRole('link', { name: '观看产品录屏' })).toHaveAttribute('href', new URL(configured).href);
  } else {
    await expect(walkthrough).toContainText('产品录屏尚未配置');
    await expect(walkthrough.locator('video, source[src$=".mp4"]')).toHaveCount(0);
    const demoConfigured = releaseEnvironment.VITE_DEMO_URL?.trim();
    await expect(walkthrough.getByRole('link', { name: demoConfigured ? '打开在线 Demo' : '查看体验方式与边界' }))
      .toHaveAttribute('href', demoConfigured ? new URL(demoConfigured).href : '#experience');
  }
  const images = walkthrough.locator('.walkthrough-gallery img');
  await expect(images).toHaveCount(7);
  for (const image of await images.all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
    expect((await image.getAttribute('alt'))?.length).toBeGreaterThan(8);
  }
});

test('engineering details expand and collapse with the keyboard', async ({ page }) => {
  const details = page.locator('.engineering-details');
  const summary = details.locator('summary');
  await expect(details.locator('#architecture')).not.toBeVisible();
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(details.locator('#architecture')).toBeVisible();
  await expect(details.locator('#evidence')).toBeVisible();
  await page.keyboard.press('Space');
  await expect(details.locator('#architecture')).not.toBeVisible();
});

test('the visible PDF download serves the approved actual PDF', async ({ page, request }) => {
  const download = page.getByRole('link', { name: /下载完整产品介绍 PDF/ });
  await expect(download).toBeVisible();
  await expect(download).toHaveAttribute('download', '');
  const url = await download.getAttribute('href');
  expect(url).toBe('/documents/Workshop-AI-Product-Introduction-Zhan-Jin.pdf');
  const response = await request.get(url!);
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toContain('application/pdf');
  expect((await response.body()).subarray(0, 5).toString()).toBe('%PDF-');
});

test('reduced motion disables smooth scrolling', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('html')).toHaveCSS('scroll-behavior', 'auto');
});

test('the footer provides direct portfolio contact details', async ({ page }) => {
  const footer = page.getByRole('contentinfo');
  await expect(footer).toContainText('Zhan Jin');
  await expect(footer.getByRole('link', { name: '15366123264' })).toHaveAttribute('href', 'tel:15366123264');
  await expect(footer.getByRole('link', { name: 'jinzhan_2023@163.com' })).toHaveAttribute('href', 'mailto:jinzhan_2023@163.com');
});
