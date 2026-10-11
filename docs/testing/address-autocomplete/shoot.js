// Captures location suggestions, selection and configuration errors.
//
// These component captures require a temporary Account row that opens the picker.
// That capture-only entry is not part of the application.
//
// MODE=live         (default) a real Places API key is configured, so the
//                    suggestions and coordinates come from Google through our
//                    own proxy.
// MODE=unconfigured  no key: the backend answers 503 and the picker shows that
//                    message. Kept because that is what a fresh clone sees.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
const OUT = __dirname;
const PASSWORD = "Demo1234";
const CUSTOMER = "demo_customer_1@workshop.ai";
const ACCOUNT_TAB = /^Account/;
const MODE = process.env.MODE === "unconfigured" ? "unconfigured" : "live";

const visible = (page, text) =>
  page.getByText(text, { exact: true }).locator("visible=true").first();
const field = (page, placeholder) =>
  page.getByPlaceholder(placeholder).locator("visible=true").first();

let failures = 0;
function check(ok, pass, fail) {
  console.log(ok ? `PASS: ${pass}` : `FAIL: ${fail}`);
  if (!ok) failures += 1;
}
async function isShown(page, text) {
  return visible(page, text).isVisible().catch(() => false);
}
async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("saved", name);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });

  await page.goto(APP, { waitUntil: "networkidle" });
  await field(page, "you@example.com").fill(CUSTOMER);
  await field(page, "Minimum 8 characters").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .waitFor({ state: "visible", timeout: 60000 });
  await page.waitForTimeout(1500);

  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2000);
  await visible(page, "Location picker (dev)").click();
  await page.waitForTimeout(1500);

  check(
    await isShown(page, "No location selected"),
    "picker opens with nothing selected",
    "picker did not open",
  );

  // Every request the picker makes must go to our own proxy.
  const placesCalls = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/places/")) placesCalls.push(url);
    if (url.includes("maps.googleapis.com")) placesCalls.push(`DIRECT:${url}`);
  });

  await field(page, "Start typing an address").fill("Taksim");
  await page.waitForTimeout(3000);

  if (MODE === "unconfigured") {
    check(
      await isShown(page, "Places service is not configured"),
      "the backend's 503 is shown to the user",
      "the configuration error was not surfaced",
    );
    await shot(page, "03-places-not-configured");
  } else {
    // Google's wording changes, so match the shape of a real result rather
    // than one exact string.
    const suggestion = page
      .getByText(/Taksim.*(Türkiye|Turkiye)/)
      .locator("visible=true")
      .first();
    check(
      (await suggestion.count()) > 0,
      "typing shows live suggestions from /places/autocomplete",
      "no suggestions came back from the proxy",
    );
    await shot(page, "01-suggestions");

    const chosen = (await suggestion.textContent()) ?? "";
    await suggestion.click();
    await page.waitForTimeout(2500);

    const coordinates = page
      .getByText(/^-?\d+\.\d{6}, -?\d+\.\d{6}$/)
      .locator("visible=true")
      .first();
    check(
      (await coordinates.count()) > 0,
      `picking "${chosen.slice(0, 40)}…" filled coordinates from /places/details (${(
        await coordinates.textContent()
      )?.trim()})`,
      "coordinates were not filled from the details call",
    );
    check(
      await page
        .getByText(/Taksim/)
        .locator("visible=true")
        .first()
        .isVisible()
        .catch(() => false),
      "the chosen place's formatted address is shown",
      "the formatted address is missing",
    );
    await shot(page, "02-selected-place");
  }

  check(
    placesCalls.length > 0 && placesCalls.every((url) => !url.startsWith("DIRECT:")),
    `only our proxy was called (${placesCalls.length} request(s), no maps.googleapis.com)`,
    `the app called Google directly: ${placesCalls.filter((u) => u.startsWith("DIRECT:")).join(", ")}`,
  );

  // There is no way to type a coordinate any more.
  check(
    (await page.getByPlaceholder("-33.8688").count()) === 0 &&
      (await page.getByPlaceholder("151.2093").count()) === 0,
    "the hand-typed latitude and longitude fields are gone",
    "coordinate inputs are still present",
  );

  await browser.close();
  console.log(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
