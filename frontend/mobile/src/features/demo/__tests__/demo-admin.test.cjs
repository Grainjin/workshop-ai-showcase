const assert = require("node:assert/strict");
const test = require("node:test");
const Module = require("node:module");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const web = require("react-native-web");
const build = "../../../../.test-build/";

function loadAdmin(enabled) {
  const original = Module._load;
  const panelEffects = [];
  Module._load = function(request, parent, ...args) {
    if (request === "react-native") return { ...web, Modal: () => null };
    if (request.endsWith("config/env")) return { DEMO_MODE: enabled, API_BASE_URL: "http://api.invalid" };
    if (request === "@react-navigation/native") return { useFocusEffect() {} };
    if (request === "lucide-react-native") return new Proxy({}, { get: () => () => null });
    // Static rendering does not run effects. Capture the genuine operator panel's
    // effects so its mount-time request can execute through the real API client.
    if (request === "react" && parent?.filename.endsWith("AISubscriptionPanel.js")) {
      return { ...React, useEffect: effect => panelEffects.push(effect) };
    }
    return original.call(this, request, parent, ...args);
  };
  try {
    for (const name of ["screens/admin/AdminDashboardScreen", "screens/admin/AISubscriptionPanel", "api/admin", "api/client"])
      delete require.cache[require.resolve(build + name + ".js")];
    return { ...require(build + "screens/admin/AdminDashboardScreen.js"),
      ...require(build + "api/client.js"), panelEffects };
  } finally {
    Module._load = original;
  }
}

for (const enabled of [true, false]) {
  test(`actual Admin dashboard isolates operator panel with Demo=${enabled}`, async () => {
    const { AdminDashboardScreen, apiClient, panelEffects } = loadAdmin(enabled);
    const requests = [];
    apiClient.defaults.adapter = async config => {
      requests.push(config.url);
      return { config, status: 200, statusText: "OK", headers: {}, data: { success: true, data: null } };
    };
    const html = renderToStaticMarkup(React.createElement(AdminDashboardScreen));
    for (const label of ["Admin dashboard", "Provider verification", "Portfolios pending review", "Refund appeals pending review"])
      assert.ok(html.includes(label), `Business admin section missing: ${label}`);
    for (const label of ["Customer AI", "Vendor API key", "Load official models"])
      assert.equal(html.includes(label), !enabled, `Operator panel visibility: ${label}`);
    for (const effect of panelEffects) effect();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(requests, enabled ? [] : ["/ai/oauth"]);
    assert.equal(panelEffects.length === 0, enabled, "Demo must not mount the status-fetching panel");
  });
}
