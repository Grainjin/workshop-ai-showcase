// Captures Account navigation, help and payment history, against the
// live API. Re-runnable against a seeded local demo.
//
// React Navigation keeps inactive screens mounted, so every locator is scoped
// to visible elements — otherwise a hidden copy on another screen matches.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
// The provider leg must use an account that actually owns a payment, or shot 07
// captures an empty state and proves nothing about the history. Payments in the
// seed belong to provider profiles 16 and 2 — not profile 1.
const PROVIDER = "demo_provider_16@workshop.ai";
const CUSTOMER = "demo_customer_1@workshop.ai";
const OUT = __dirname;
const PASSWORD = "Demo1234";
// The Account tab carries the unread badge, so its accessible name is "Account"
// or "Account 1". An exact match silently fails for any account with unread
// notifications — match the prefix instead.
const ACCOUNT_TAB = /^Account/;

const visible = (page, text) =>
  page.getByText(text, { exact: true }).locator("visible=true").first();

async function signIn(page, email) {
  await page.goto(APP, { waitUntil: "networkidle" });
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("Minimum 8 characters").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  // Waiting for the shell to actually appear beats a fixed sleep: a second
  // sign-in after signing out is slower than the first.
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .waitFor({ state: "visible", timeout: 60000 });
  await page.waitForTimeout(1500);
}

async function openAccountTab(page) {
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2500);
}

async function openRow(page, label) {
  await visible(page, label).click();
  await page.waitForTimeout(2500);
}

// The web build does not push a history entry per screen, so goBack() does
// nothing here. Tapping the sidebar's Account item pops back to the tab.
async function back(page) {
  await openAccountTab(page);
}

// A screenshot of an empty list is not evidence that history works, so fail
// loudly rather than committing a blank screen.
async function assertHasPayments(page, role) {
  const empty = await visible(page, "No payments yet")
    .isVisible()
    .catch(() => false);
  console.log(
    empty
      ? `FAIL: ${role} payment history is empty — wrong account, or the query broke`
      : `PASS: ${role} payment history shows records`,
  );
}

async function shot(page, name) {
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log("saved", name);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 820 } });

  await signIn(page, CUSTOMER);
  await openAccountTab(page);
  await shot(page, "01-account-customer");

  await openRow(page, "Payments");
  await assertHasPayments(page, "customer");
  await shot(page, "02-payments-customer");
  await back(page);

  await openRow(page, "Help and Support");
  await shot(page, "03-help-and-support");
  await back(page);

  await openRow(page, "Notification settings");
  await shot(page, "04-notification-settings");
  await back(page);

  await openRow(page, "Favourites");
  await shot(page, "05-favourites-customer");
  await back(page);

  await openRow(page, "Sign out");
  await page.waitForTimeout(4500);

  await signIn(page, PROVIDER);
  await openAccountTab(page);
  await shot(page, "06-account-provider");

  const favouritesVisible = await visible(page, "Favourites")
    .isVisible()
    .catch(() => false);
  console.log(
    favouritesVisible
      ? "FAIL: provider can see Favourites"
      : "PASS: Favourites hidden for provider",
  );

  await openRow(page, "Payments");
  await assertHasPayments(page, "provider");
  await shot(page, "07-payments-provider");

  await browser.close();
})();
