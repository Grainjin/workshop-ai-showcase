// Captures legal-page entry points against the live app. Re-runnable.
//
// React Navigation keeps inactive screens mounted, so every locator is scoped
// to visible elements — otherwise a hidden copy on another screen matches.
const { chromium } = require("playwright");

const APP = "http://localhost:8090";
const OUT = __dirname;
const PASSWORD = "Demo1234";
const CUSTOMER = "demo_customer_1@workshop.ai";
// A provider with a complete profile, so the profile gate does not bounce them
// away from Help and Support before the legal links can be reached.
const PROVIDER = "demo_provider_16@workshop.ai";
// Unread badges turn the tab's name into "Account 1"; match the prefix.
const ACCOUNT_TAB = /^Account/;

const visible = (page, text) =>
  page.getByText(text, { exact: true }).locator("visible=true").first();

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

async function openSignedOut(page) {
  await page.goto(APP, { waitUntil: "networkidle" });
  await page.getByPlaceholder("you@example.com").waitFor({ timeout: 60000 });
}

async function signIn(page, email) {
  await openSignedOut(page);
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("Minimum 8 characters").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .waitFor({ state: "visible", timeout: 60000 });
  await page.waitForTimeout(1500);
}

async function openLegalFromHelp(page, linkText) {
  await page
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await page.waitForTimeout(2000);
  await visible(page, "Help and Support").click();
  await page.waitForTimeout(2000);
  await visible(page, linkText).click();
  await page.waitForTimeout(2000);
}

// The headings are the page's content; comparing them is how "both roles see
// the same page" is checked, rather than by eye.
async function visibleHeadings(page, headings) {
  const shown = [];
  for (const heading of headings) {
    if (await isShown(page, heading)) shown.push(heading);
  }
  return shown.join(" | ");
}

const PRIVACY_HEADINGS = ["What we collect", "How we use it", "Who can see it", "Your choices"];
const TERMS_HEADINGS = ["Using Workshop AI", "Bookings and payments", "Reviews and content", "Changes"];

(async () => {
  const browser = await chromium.launch();
  const viewport = { width: 1100, height: 820 };

  // --- Signed out: register happens here, so the pages must open without a session.
  const out = await browser.newPage({ viewport });
  await openSignedOut(out);
  check(
    (await isShown(out, "Privacy Policy")) && (await isShown(out, "Terms of Use")),
    "sign-in screen links to both legal pages",
    "legal links missing from the sign-in screen",
  );
  await shot(out, "01-auth-legal-links");

  await visible(out, "Privacy Policy").click();
  await out.waitForTimeout(2000);
  check(await isShown(out, "Demo only"), "Privacy opens signed out, marked Demo only", "Privacy did not open signed out");
  check(
    (await visibleHeadings(out, PRIVACY_HEADINGS)) === PRIVACY_HEADINGS.join(" | "),
    "Privacy shows placeholder sections",
    "Privacy sections missing",
  );
  await shot(out, "02-privacy-signed-out");

  await openSignedOut(out);
  await visible(out, "Terms of Use").click();
  await out.waitForTimeout(2000);
  check(await isShown(out, "Demo only"), "Terms opens signed out, marked Demo only", "Terms did not open signed out");
  const signedOutTerms = await visibleHeadings(out, TERMS_HEADINGS);
  await shot(out, "03-terms-signed-out");
  await out.close();

  // --- Customer, signed in: same pages from Help and Support.
  const customer = await browser.newPage({ viewport });
  await signIn(customer, CUSTOMER);
  await openLegalFromHelp(customer, "Terms of Use");
  const customerTerms = await visibleHeadings(customer, TERMS_HEADINGS);
  await shot(customer, "04-terms-customer");
  await customer.close();

  // --- Provider, signed in.
  const provider = await browser.newPage({ viewport });
  await signIn(provider, PROVIDER);
  await provider
    .getByRole("button", { name: ACCOUNT_TAB })
    .locator("visible=true")
    .first()
    .click();
  await provider.waitForTimeout(2000);
  await visible(provider, "Help and Support").click();
  await provider.waitForTimeout(2000);
  await shot(provider, "05-help-legal-section-provider");
  await visible(provider, "Terms of Use").click();
  await provider.waitForTimeout(2000);
  const providerTerms = await visibleHeadings(provider, TERMS_HEADINGS);
  await shot(provider, "06-terms-provider");
  await provider.close();

  check(
    signedOutTerms === TERMS_HEADINGS.join(" | ") &&
      customerTerms === signedOutTerms &&
      providerTerms === signedOutTerms,
    "signed out, customer and provider see the same Terms page",
    `Terms differ — signed out [${signedOutTerms}] customer [${customerTerms}] provider [${providerTerms}]`,
  );

  await browser.close();
  console.log(failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
