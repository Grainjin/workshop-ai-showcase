const assert = require("node:assert/strict");
const test = require("node:test");
const Module = require("node:module");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const web = require("react-native-web");

function loadComponents(enabled) {
  const originalLoad = Module._load;
  Module._load = function (request, ...args) {
    if (request === "react-native") return web;
    if (request === "react-native-safe-area-context") return { SafeAreaView: web.View };
    if (request === "../config/env") return { DEMO_MODE: enabled };
    return originalLoad.call(this, request, ...args);
  };
  try {
    const rolesPath = "../../../../.test-build/components/DemoRoleButtons.js";
    const bannerPath = "../../../../.test-build/components/PublicDemoBanner.js";
    delete require.cache[require.resolve(rolesPath)];
    delete require.cache[require.resolve(bannerPath)];
    return { ...require(rolesPath), ...require(bannerPath) };
  } finally {
    Module._load = originalLoad;
  }
}

test("ordinary mode renders neither demo controls nor simulation banner", () => {
  const { DemoRoleButtons, PublicDemoBanner } = loadComponents(false);
  assert.equal(renderToStaticMarkup(React.createElement(DemoRoleButtons, { onSignIn: async () => {} })), "");
  assert.equal(renderToStaticMarkup(React.createElement(PublicDemoBanner)), "");
});

test("demo role controls render ordered accessible buttons and their purposes", () => {
  const { DemoRoleButtons } = loadComponents(true);
  const html = renderToStaticMarkup(React.createElement(DemoRoleButtons, { onSignIn: async () => {} }));
  assert.equal((html.match(/role="button"/g) || []).length, 3);
  assert.ok(html.indexOf("Customer") < html.indexOf("Provider"));
  assert.ok(html.indexOf("Provider") < html.indexOf("Admin"));
  for (const role of ["Customer", "Provider", "Admin"]) assert.ok(html.includes(`aria-label="Try the ${role} demo.`));
  assert.match(html, /Find providers and book a service/);
});

test("persistent banner discloses simulated data and payments without auth dependence", () => {
  const { PublicDemoBanner } = loadComponents(true);
  const html = renderToStaticMarkup(React.createElement(PublicDemoBanner));
  assert.match(html, /Public Demo/);
  assert.match(html, /simulated data and payments/);
  assert.match(html, /aria-label="Public Demo/);
});
