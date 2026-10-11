// Historical capture helper, not a current acceptance test. See README.
// Its placeholder verification code and demo-hint assertions are obsolete;
// current verification requires the actual delivered code before reuse.
//
// React Navigation keeps inactive screens mounted, so every locator is scoped
// to visible elements — otherwise a hidden copy on another screen matches.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
const OUT = __dirname;
const PASSWORD = "Demo1234";
const CUSTOMER = "demo_customer_1@workshop.ai";
// A provider with a complete profile, so the profile gate does not bounce them away
// from Account before the security screen is reached.
const PROVIDER = "demo_provider_16@workshop.ai";
// Destructive checks (real password / email change) run on a separate account
// so the accounts used for demos keep their seeded credentials.
const SPARE = "demo_customer_5@workshop.ai";
const SPARE_NEW_EMAIL = "demo_customer_5_changed@workshop.ai";
const SPARE_NEW_PASSWORD = "Demo12345";
// Unread badges turn the tab's name into "Account 1"; match the prefix.
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

// The spare account's password and email are changed by this script, so a
// re-run must tolerate either state and put both back before it finishes.
async function signInWithFallback(page, email, passwords) {
  for (const password of passwords) {
    try {
      await signIn(page, email, password);
      return password;
    } catch (error) {
      if (password === passwords[passwords.length - 1]) throw error;
    }
  }
  return null;
}

async function changePasswordInUi(page, current, next) {
  await field(page, "Your current password").fill(current);
  await field(page, "Minimum 8 characters").fill(next);
  await field(page, "Repeat the new password").fill(next);
  await page.getByRole("button", { name: "Update password" }).click();
  await page.waitForTimeout(3000);
}

async function changeEmailInUi(page, nextEmail) {
  await field(page, "you@example.com").fill(nextEmail);
  await page.getByRole("button", { name: "Send code" }).click();
  await page.waitForTimeout(1200);
  await submitCode(page);
}

async function signIn(page, email, password = PASSWORD) {
  await page.goto(APP, { waitUntil: "networkidle" });
  await field(page, "you@example.com").fill(email);
  await field(page, "Minimum 8 characters").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .waitFor({ state: "visible", timeout: 60000 });
  await page.waitForTimeout(1500);
}

async function openSecurity(page) {
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2000);
  await visible(page, "Account and Security").click();
  await page.waitForTimeout(2000);
}

// The verification modal asks for six digits and shows the demo hint.
async function submitCode(page, code = "123456") {
  await field(page, "123456").fill(code);
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.waitForTimeout(2500);
}

(async () => {
  const browser = await chromium.launch();
  const viewport = { width: 1100, height: 900 };

  // --- Customer: the screen and the verification flow.
  const customer = await browser.newPage({ viewport });
  await signIn(customer, CUSTOMER);
  await openSecurity(customer);
  check(
    await isShown(customer, "Account and Security"),
    "customer reaches Account and Security",
    "customer cannot reach the security screen",
  );
  await shot(customer, "01-security-customer");

  await customer.getByRole("button", { name: "Verify email" }).click();
  await customer.waitForTimeout(1200);
  check(
    await isShown(customer, "Enter any 6 digits. Demo only."),
    "verify modal shows the demo hint",
    "demo hint missing from the verify modal",
  );
  await shot(customer, "02-verify-modal");

  await submitCode(customer);
  check(
    await isShown(customer, "Email verified."),
    "any 6 digits verifies the email",
    "verification did not succeed",
  );
  await shot(customer, "03-email-verified");

  // --- Wrong current password must be rejected by the backend.
  await field(customer, "Your current password").fill("WrongPass123");
  await field(customer, "Minimum 8 characters").fill(SPARE_NEW_PASSWORD);
  await field(customer, "Repeat the new password").fill(SPARE_NEW_PASSWORD);
  await customer.getByRole("button", { name: "Update password" }).click();
  await customer.waitForTimeout(2500);
  check(
    await isShown(customer, "Current password is incorrect"),
    "wrong current password is rejected",
    "wrong current password did not produce an error",
  );
  await shot(customer, "04-wrong-current-password");

  // --- Mismatched new passwords are caught before any request.
  await field(customer, "Your current password").fill(PASSWORD);
  await field(customer, "Minimum 8 characters").fill(SPARE_NEW_PASSWORD);
  await field(customer, "Repeat the new password").fill("Different123");
  await customer.getByRole("button", { name: "Update password" }).click();
  await customer.waitForTimeout(1200);
  check(
    await isShown(customer, "The new passwords do not match."),
    "mismatched new passwords are blocked",
    "mismatched passwords were not blocked",
  );
  await shot(customer, "05-password-mismatch");
  await customer.close();

  // --- Spare account: a real password change and a real email change.
  const spare = await browser.newPage({ viewport });
  await signInWithFallback(spare, SPARE, [PASSWORD, SPARE_NEW_PASSWORD]);
  await openSecurity(spare);

  await changePasswordInUi(spare, PASSWORD, SPARE_NEW_PASSWORD);
  check(
    await isShown(spare, "Password changed. Other devices are signed out and will need the new password."),
    "password change succeeds and the session survives",
    "password change did not succeed",
  );
  await shot(spare, "06-password-changed");

  await changeEmailInUi(spare, SPARE_NEW_EMAIL);
  check(
    await isShown(spare, `Sign-in email changed to ${SPARE_NEW_EMAIL}.`),
    "change email confirmed with the demo code",
    "change email did not succeed",
  );
  await shot(spare, "07-email-changed");

  // Put the spare account back so the next run starts from the seeded state.
  await changeEmailInUi(spare, SPARE);
  await changePasswordInUi(spare, SPARE_NEW_PASSWORD, PASSWORD);
  check(
    await isShown(spare, "Password changed. Other devices are signed out and will need the new password."),
    "spare account restored to its seeded email and password",
    "spare account was left changed — fix before re-running",
  );
  await spare.close();

  // --- Provider sees the same screen.
  const provider = await browser.newPage({ viewport });
  await signIn(provider, PROVIDER);
  await openSecurity(provider);
  check(
    await isShown(provider, "Account and Security"),
    "provider reaches the same security screen",
    "provider cannot reach the security screen",
  );
  await shot(provider, "08-security-provider");
  await provider.close();

  await browser.close();
  console.log(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
