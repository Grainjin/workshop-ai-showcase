import { expect, test, type Page } from 'playwright/test';
import { loadViteReleaseEnvironment } from './vite-release-environment';

const releaseTargets = [
  { label: '在线体验', variable: 'VITE_DEMO_URL', fallback: '#release-status' },
  { label: '观看 Demo', variable: 'VITE_VIDEO_URL', fallback: '#walkthrough' },
  { label: '查看 GitHub', variable: 'VITE_GITHUB_URL', fallback: '#release-status' },
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

test('the page fits the viewport and loads without browser errors', async ({ page }) => {
  await page.locator('footer').scrollIntoViewIfNeeded();
  await expect(page.locator('.walkthrough-gallery img')).toHaveCount(2);
  await expect.poll(() => page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.documentElement.clientWidth,
  }))).toEqual({ document: 0, body: 0 });
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

test('primary actions lead to configured URLs or the release explanation', async ({ page }) => {
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
    await expect(walkthrough.getByRole('link', { name: '观看已配置产品录屏' })).toHaveAttribute('href', new URL(configured).href);
    await expect(walkthrough).toContainText('产品录屏入口已配置');
  } else {
    await expect(walkthrough).toContainText('60–90 秒录屏准备中');
    await expect(walkthrough.locator('video, source[src$=".mp4"]')).toHaveCount(0);
    await expect(walkthrough.getByRole('link', { name: '查看 Live Demo 准备状态' })).toHaveAttribute('href', '#release-status');
  }
  const images = walkthrough.locator('.walkthrough-gallery img');
  await expect(images).toHaveCount(2);
  for (const image of await images.all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
    await expect(image).toHaveAttribute('alt', /历史验证截图/);
  }
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
