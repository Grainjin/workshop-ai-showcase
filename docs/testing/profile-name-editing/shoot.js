// Historical capture helper; review README prerequisites and selectors before reuse.
// Captured split-name editing and legacy display-name compatibility.
//
// The historical runs used these API shapes:
//   MODE=fallback  (default) the user object has no first_name,
//                  so the screen PATCHes the joined name.
//   MODE=split     the split-name API: the user object
//                  carries first_name, so the screen PATCHes the split fields.
//
// Either way users.name stays the joined display string, which is what chat and
// bookings read.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
const OUT = __dirname;
const PASSWORD = "Demo1234";
const CUSTOMER = "demo_customer_1@workshop.ai";
const ACCOUNT_TAB = /^Account/;
const MODE = process.env.MODE === "split" ? "split" : "fallback";

const ORIGINAL_FIRST = "Istanbul";
const ORIGINAL_LAST = "Customer 1";
const EDITED_LAST = "Customer One";

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

async function openAccount(page) {
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2000);
}

async function openEdit(page) {
  await openAccount(page);
  await visible(page, "Edit profile").click();
  await page.waitForTimeout(2500);
}

async function saveLastName(page, nextLast) {
  await field(page, "Your last name").fill(nextLast);
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForTimeout(3000);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 950 } });

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

  // --- The joined display name arrives split across two fields.
  await openEdit(page);
  check(
    (await field(page, "Your first name").inputValue()) === ORIGINAL_FIRST &&
      (await field(page, "Your last name").inputValue()) === ORIGINAL_LAST,
    `edit shows the name split: ${ORIGINAL_FIRST} / ${ORIGINAL_LAST}`,
    "the name was not split across the two fields",
  );
  await shot(page, `01-edit-split-${MODE}`);

  // --- An empty half is rejected before any request.
  await field(page, "Your last name").fill("");
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForTimeout(1200);
  check(
    await isShown(page, "Fill in the required fields."),
    "an empty last name blocks the save",
    "an empty last name was accepted",
  );
  await shot(page, `02-last-name-required-${MODE}`);

  // --- Saving keeps users.name as the joined string.
  await saveLastName(page, EDITED_LAST);
  await openAccount(page);
  check(
    await isShown(page, `${ORIGINAL_FIRST} ${EDITED_LAST}`),
    `saving joins the two fields back into the display name (${ORIGINAL_FIRST} ${EDITED_LAST})`,
    "the display name did not pick up the edit",
  );
  await shot(page, `03-saved-${MODE}`);

  // --- Put the account back so the script can be re-run.
  await openEdit(page);
  await saveLastName(page, ORIGINAL_LAST);
  await openAccount(page);
  check(
    await isShown(page, `${ORIGINAL_FIRST} ${ORIGINAL_LAST}`),
    "the demo account is restored",
    "the demo account was left renamed — fix before re-running",
  );

  await browser.close();
  console.log(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
