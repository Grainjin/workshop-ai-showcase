// Run after a Demo web export. Uses the monorepo's existing browser-test tooling.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const http = require("node:http");
const { readFile } = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("../../../showcase/site/node_modules/playwright");

const dist = path.resolve(__dirname, "..", process.env.WORKSHOP_STATUS_TEST_DIST || "dist");
let server, browser, origin;

before(async () => {
  server = http.createServer(async (request, response) => {
    const pathname = new URL(request.url, "http://local.test").pathname;
    const file = path.resolve(dist, "." + pathname);
    if (!file.startsWith(dist + path.sep) && file !== dist) {
      response.writeHead(404).end();
      return;
    }
    try {
      const body = await readFile(pathname === "/" ? path.join(dist, "index.html") : file);
      response.setHeader("Content-Type", file.endsWith(".js") ? "application/javascript" :
        file.endsWith(".css") ? "text/css" : pathname === "/" ? "text/html" : "application/octet-stream");
      response.end(body);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
});

after(async () => {
  await browser?.close();
  await new Promise(resolve => server?.close(resolve));
});

const readiness = (overrides = {}) => ({
  success: true, message: "Success", data: {
    status: "degraded", ready: true, database: "available", demo_mode: true,
    payment_mode: "demo", ai_configured: false, degraded_services: ["ai"], ...overrides,
  },
});

async function withPage(handler, run, waitForReady = false) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/ready", handler);
  try {
    const readyResponse = waitForReady
      ? page.waitForResponse(response => response.url().endsWith("/ready") && response.status() === 200)
      : null;
    await page.goto(origin);
    await page.getByRole("button", { name: /Try the Customer demo/ }).waitFor();
    if (readyResponse) {
      await (await readyResponse).finished();
      await page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    await run(page);
    assert.deepEqual(errors, [], "Status failures must not create unhandled errors");
  } finally {
    await page.close();
  }
}

const fulfill = (body, status = 200) => route => route.fulfill({
  status, contentType: "application/json", headers: { "Access-Control-Allow-Origin": origin },
  body: JSON.stringify(body),
});

test("degraded AI is disclosed, dismissible, and does not block the actual demo login control", async () => {
  await withPage(fulfill(readiness()), async page => {
    await page.getByText("AI assistance is unavailable. You can still browse, book, and use simulated payments.").waitFor({ timeout: 5000 });
    let loginRequests = 0;
    await page.route("**/demo/login", route => {
      if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204,
        headers: { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST",
          "Access-Control-Allow-Headers": "content-type" } });
      loginRequests++;
      assert.equal(route.request().method(), "POST");
      assert.deepEqual(route.request().postDataJSON(), { role: "customer" });
      return route.fulfill({ status: 503, contentType: "application/json",
        headers: { "Access-Control-Allow-Origin": origin },
        body: JSON.stringify({ success: false, message: "Fixture login reached" }) });
    });
    await page.getByRole("button", { name: /Try the Customer demo/ }).click();
    await page.getByText("Demo sign-in is unavailable. Please try again.").waitFor({ timeout: 5000 });
    assert.equal(loginRequests, 1);
    await page.getByRole("button", { name: "Dismiss service status" }).click();
    assert.equal(await page.getByRole("status").count(), 0);
    assert.equal(await page.getByRole("button", { name: /Try the Customer demo/ }).count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  });
});

test("an unavailable database produces a dismissible service notice with core controls still visible", async () => {
  await withPage(fulfill(readiness({ status: "not_ready", ready: false, database: "unavailable",
    degraded_services: ["database", "ai"] }), 503), async page => {
    await page.getByText("The service is temporarily unavailable. Please try again later.").waitFor({ timeout: 5000 });
    await page.getByRole("button", { name: "Dismiss service status" }).click();
    assert.equal(await page.getByRole("status").count(), 0);
  });
});

test("network or CORS denial is caught and yields a generic dismissible notice", async () => {
  await withPage(route => route.abort("blockedbyclient"), async page => {
    await page.getByText("We could not check service availability. Please try again later.").waitFor({ timeout: 5000 });
    await page.getByRole("button", { name: "Dismiss service status" }).click();
    assert.equal(await page.getByRole("status").count(), 0);
  });
});

test("malformed readiness is handled without rendering raw server diagnostics", async () => {
  await withPage(fulfill({ secret: "private-diagnostic" }), async page => {
    await page.getByText("We could not check service availability. Please try again later.").waitFor({ timeout: 5000 });
    assert.equal(await page.getByText("private-diagnostic").count(), 0);
  });
});

test("healthy configured readiness needs no banner", async () => {
  await withPage(fulfill(readiness({ status: "ready", ai_configured: true, degraded_services: [] })), async page => {
    // /ready has completed and the browser has rendered subsequent frames.
    assert.equal(await page.getByRole("status").count(), 0);
  }, true);
});
