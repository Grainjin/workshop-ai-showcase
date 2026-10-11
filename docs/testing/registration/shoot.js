// Captures registration validation and legal links, against the live
// API. Re-runnable: each run registers a fresh address.
//
// Existing-account editing is covered by the separate profile-edit captures.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
const OUT = __dirname;
const PASSWORD = "Demo1234";
const FIRST_NAME = "Ada";
const LAST_NAME = "Lovelace";
const NEW_EMAIL = `registration_${Date.now()}@workshop.ai`;
const ACCOUNT_TAB = /^Account/;

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

// Each case starts from a freshly loaded form, so the tick state is always
// known: reading it back from the DOM proved unreliable.
async function openRegisterForm(page) {
  await page.goto(APP, { waitUntil: "networkidle" });
  await visible(page, "Don't have an account? Create one").click();
  await page.waitForTimeout(1200);
}

async function fillRegisterForm(page, { email, confirm, acceptTerms }) {
  await field(page, "Your first name").fill(FIRST_NAME);
  await field(page, "Your last name").fill(LAST_NAME);
  await field(page, "you@example.com").fill(email);
  await field(page, "Minimum 8 characters").fill(PASSWORD);
  await field(page, "Repeat your password").fill(confirm);

  if (acceptTerms) {
    // Tapping the row toggles it; the links inside open the legal pages.
    await page
      .getByRole("checkbox")
      .locator("visible=true")
      .first()
      .click({ position: { x: 11, y: 11 } });
    await page.waitForTimeout(400);
  }
}

async function submitRegister(page) {
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForTimeout(1800);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 950 } });

  // --- The form itself.
  await openRegisterForm(page);
  check(
    (await isShown(page, "First name")) && (await isShown(page, "Last name")),
    "register asks for first name and last name",
    "the split name fields are missing",
  );
  check(
    await isShown(page, "Confirm password"),
    "register asks to confirm the password",
    "the confirm password field is missing",
  );
  await shot(page, "01-register-form");

  // --- Mismatched passwords must block the submit.
  await fillRegisterForm(page, {
    email: NEW_EMAIL,
    confirm: "Different123",
    acceptTerms: true,
  });
  await submitRegister(page);
  check(
    await isShown(page, "The passwords do not match."),
    "mismatched passwords block the submit",
    "mismatched passwords were not blocked",
  );
  await shot(page, "02-password-mismatch");

  // --- An unticked Terms box must block the submit.
  await openRegisterForm(page);
  await fillRegisterForm(page, {
    email: NEW_EMAIL,
    confirm: PASSWORD,
    acceptTerms: false,
  });
  await submitRegister(page);
  check(
    await isShown(page, "Please accept the Terms of Use to continue."),
    "an unticked Terms box blocks the submit",
    "registration went ahead without accepting the Terms",
  );
  await shot(page, "03-terms-required");

  // --- The Terms link opens the legal page.
  await visible(page, "Terms of Use").click();
  await page.waitForTimeout(2200);
  check(
    await isShown(page, "Demo only"),
    "the Terms link opens the legal page",
    "the Terms link did not open the legal page",
  );
  await shot(page, "04-terms-page-from-checkbox");

  // --- A complete, accepted form registers and signs in.
  await openRegisterForm(page);
  await fillRegisterForm(page, {
    email: NEW_EMAIL,
    confirm: PASSWORD,
    acceptTerms: true,
  });
  await submitRegister(page);
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .waitFor({ state: "visible", timeout: 60000 });
  await page.waitForTimeout(1500);
  check(true, `registered ${NEW_EMAIL} and signed in`, "registration failed");

  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2500);
  check(
    await isShown(page, `${FIRST_NAME} ${LAST_NAME}`),
    "the joined display name is what chat and bookings will read",
    "the display name was not the two names joined",
  );
  await shot(page, "05-registered-account");

  await browser.close();
  console.log(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
