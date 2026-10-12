// Run against a local production Expo export; never contact a live API.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const http = require("node:http");
const { readFile } = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("../../../showcase/site/node_modules/playwright");

const dist = path.resolve(__dirname, "../dist");
const origin = "http://127.0.0.1:18550";
let server, browser;

before(async () => {
  server = http.createServer(async (request, response) => {
    const pathname = new URL(request.url, origin).pathname;
    const file = path.resolve(dist, "." + pathname);
    if (!file.startsWith(dist + path.sep) && file !== dist) {
      response.writeHead(404).end();
      return;
    }
    try {
      const isAppPath = pathname === "/" || pathname === "/payment-result";
      const body = await readFile(isAppPath ? path.join(dist, "index.html") : file);
      response.setHeader("Content-Type", isAppPath ? "text/html" :
        file.endsWith(".js") ? "application/javascript" :
        file.endsWith(".css") ? "text/css" : "application/octet-stream");
      response.end(body);
    } catch {
      response.writeHead(404).end();
    }
  });
  // Bind itself is the authoritative availability check. Never reuse another
  // process's port or terminate it; EADDRINUSE fails this task-owned harness.
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(18550, "127.0.0.1", resolve);
  });
  browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
});

after(async () => {
  await browser?.close();
  if (server?.listening) await new Promise(resolve => server.close(resolve));
});

async function withPage(run) {
  const page = await browser.newPage();
  page.setDefaultTimeout(5000);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/demo/login") return route.fulfill({
      status: route.request().method() === "OPTIONS" ? 204 : 503,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "content-type" },
      body: route.request().method() === "OPTIONS" ? "" :
        JSON.stringify({ success: false, message: "Local responsiveness fixture" }),
    });
    if (url.pathname === "/ready") return route.fulfill({
      status: 200, contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": origin },
      body: JSON.stringify({ success: true, data: {
        status: "ready", ready: true, database: "available", demo_mode: true,
        payment_mode: "demo", ai_configured: true, degraded_services: [],
      } }),
    });
    if (url.origin === origin) return route.continue();
    return route.abort("blockedbyclient");
  });
  await page.addInitScript(() => {
    window.navigationTestPopPaths = [];
    addEventListener("popstate", () => {
      window.navigationTestPopPaths.push(location.pathname + location.search);
    });
  });
  try {
    await run(page);
    assert.deepEqual(errors, [], "Navigation must not throw unhandled browser errors");
  } catch (error) {
    console.error("Local navigation diagnostic:", await page.evaluate(() => ({
      path: location.pathname + location.search,
      popPaths: window.navigationTestPopPaths,
      text: document.body.innerText,
    })));
    throw error;
  } finally {
    await page.close();
  }
}

async function responsiveFallback(page) {
  await page.getByRole("button", { name: /Try the Customer demo/ }).waitFor();
  // Real frames and a handled UI action prove both the JS event loop and application
  // interaction work after the malformed URL has traversed navigation.
  await page.evaluate(() => new Promise(resolve =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const customer = page.getByRole("button", { name: /Try the Customer demo/ });
  await customer.click();
  await page.getByText("Demo sign-in is unavailable. Please try again.").waitFor();
  assert.equal(await customer.isEnabled(), true);
  assert.equal(await page.getByText("Payment callback received").isVisible(), false);
}

for (const raw of [
  "/payment-result?x=%FF", "/payment-result?x=" + "%FF".repeat(64),
  "/payment-result?%FF=value", "/payment-result?x=%E0%A4",
]) {
  test(`malformed initial URL falls back responsively: ${raw.slice(0, 60)}`, async () => {
    await withPage(async page => {
      await page.goto(origin + raw, { timeout: 5000 });
      await responsiveFallback(page);
    });
  });
}

test("valid payment initial URL and sign-in navigation retain behavior", async () => {
  await withPage(async page => {
    await page.goto(origin + "/payment-result?booking_id=301&status=success", { timeout: 5000 });
    await page.getByText("Payment callback received").waitFor();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await responsiveFallback(page);
  });
});

for (const direction of ["back", "forward"]) {
  test(`malformed real history ${direction} navigation falls back responsively`, async () => {
    await withPage(async page => {
      await page.goto(origin + "/payment-result?booking_id=301", { timeout: 5000 });
      await page.getByText("Payment callback received").waitFor();
      await page.waitForFunction(() => localStorage.getItem("workshop_ai_pending_payment_result") !== null);
      const malformed = "/payment-result?x=" + "%FF".repeat(64);
      await page.evaluate(({ malformed, direction }) => {
        history.pushState({}, "", malformed);
        if (direction === "back") {
          history.pushState({}, "", "/payment-result?booking_id=302");
          history.back();
        } else {
          history.back();
        }
      }, { malformed, direction });
      if (direction === "forward") {
        await page.waitForFunction(() => window.navigationTestPopPaths.length > 0);
        await page.evaluate(() => history.forward());
      }
      await page.waitForFunction(raw => window.navigationTestPopPaths.includes(raw), malformed);
      await page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      // React Navigation ignores an undefined reset on history traversal and
      // retains the current screen. Refusal must not overwrite its valid params.
      assert.deepEqual(await page.evaluate(() => JSON.parse(
        localStorage.getItem("workshop_ai_pending_payment_result"),
      )), { booking_id: "301" });
      await page.getByText("Payment callback received").waitFor();
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await responsiveFallback(page);
    });
  });
}
