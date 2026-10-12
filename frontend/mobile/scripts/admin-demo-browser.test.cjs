// Genuine production-export rendering with only external transport replaced.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const http = require("node:http");
const { readFile } = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("../../../showcase/site/node_modules/playwright");
const dist = path.resolve(__dirname, "../dist");
const origin = "http://127.0.0.1:18560";
let server, browser;

before(async () => {
  server = http.createServer(async (request, response) => {
    const pathname = new URL(request.url, origin).pathname;
    const file = path.resolve(dist, "." + pathname);
    if (!file.startsWith(dist + path.sep) && file !== dist) return response.writeHead(404).end();
    try {
      const body = await readFile(pathname === "/" ? path.join(dist, "index.html") : file);
      response.setHeader("Content-Type", pathname === "/" ? "text/html" :
        file.endsWith(".js") ? "application/javascript" :
        file.endsWith(".css") ? "text/css" : "application/octet-stream");
      response.end(body);
    } catch { response.writeHead(404).end(); }
  });
  // Exclusive bind verifies availability; never reuse or stop another process.
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(18560, "127.0.0.1", resolve);
  });
  browser = await chromium.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true,
  });
});
after(async () => {
  await browser?.close();
  if (server?.listening) await new Promise(resolve => server.close(resolve));
});

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`production Demo admin has business dashboard without operator reads (${viewport.width})`, async () => {
    const page = await browser.newPage({ viewport });
    const requests = [], errors = [], unexpected = [];
    const user = { id: 1, name: "Synthetic Admin", first_name: "Synthetic", last_name: "Admin",
      email: "admin@example.invalid", role: "admin", email_verified: true,
      is_active: true, tos_accepted: true, avatar_url: null, phone_number: null };
    const paginated = { items: [], total: 0, page: 1, page_size: 20, total_pages: 1 };
    const fixtures = {
      "/ready": { status: "ready", ready: true, database: "available", demo_mode: true,
        payment_mode: "demo", ai_configured: true, degraded_services: [] },
      "/demo/login": { access_token: "synthetic-only", refresh_token: "synthetic-only", token_type: "bearer", user },
      "/notifications/summary": { unread_count: 0 },
      "/admin/provider-portfolios": paginated, "/admin/refund-requests": paginated,
      "/admin/submerchants": paginated, "/admin/payments": paginated,
      "/admin/identity-verifications": [], "/admin/qualification-verifications": [],
    };
    page.on("pageerror", error => errors.push(error.message));
    await page.routeWebSocket("**/*", socket => socket.close());
    await page.route("**/*", route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === origin) return route.continue();
      if (url.hostname !== "api.invalid") {
        unexpected.push(url.origin + url.pathname);
        return route.abort("blockedbyclient");
      }
      const headers = { "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "content-type, authorization" };
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
      requests.push(url.pathname);
      if (!(url.pathname in fixtures)) {
        unexpected.push(url.pathname);
        return route.fulfill({ status: 404, headers, body: "{}" });
      }
      if (url.pathname === "/demo/login") assert.deepEqual(request.postDataJSON(), { role: "admin" });
      return route.fulfill({ status: 200, headers, contentType: "application/json",
        body: JSON.stringify({ success: true, message: "Local fixture", data: fixtures[url.pathname] }) });
    });
    try {
      await page.goto(origin);
      await page.getByRole("button", { name: /Try the Admin demo/ }).click();
      await page.getByText("Admin dashboard", { exact: true }).waitFor();
      await page.getByText("No portfolios pending review", { exact: true }).waitFor();
      await page.getByText("No identity applications pending review.", { exact: true }).waitFor();
      await page.getByText("No refund appeals", { exact: true }).waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      for (const label of ["Customer AI", "API key", "Load official models", "Save and use"])
        assert.equal(await page.getByText(label, { exact: true }).count(), 0, `Operator control visible: ${label}`);
      assert.equal(await page.getByPlaceholder("Vendor API key").count(), 0);
      assert.equal(requests.some(item => item.startsWith("/ai/oauth")), false);
      assert.ok(requests.includes("/admin/payments"));
      assert.ok(requests.includes("/admin/qualification-verifications"));
      assert.deepEqual(unexpected, [], "Only controlled non-routable API fixtures may be requested");
      assert.deepEqual(errors, []);
    } finally { await page.close(); }
  });
}
