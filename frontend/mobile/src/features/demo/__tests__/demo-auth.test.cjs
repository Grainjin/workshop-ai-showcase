const assert = require("node:assert/strict");
const test = require("node:test");
const Module = require("node:module");
const axios = require("axios");

// Native platform detection is unavailable in Node; keep the HTTP client real.
const originalLoad = Module._load;
Module._load = function (request, ...args) {
  if (request === "react-native") return { Platform: { OS: "web" } };
  return originalLoad.call(this, request, ...args);
};
const { loginWithDemoRole } = require("../../../../.test-build/api/auth.js");
const { apiClient, getAccessToken, setSessionTokens } = require("../../../../.test-build/api/client.js");
Module._load = originalLoad;

const user = {
  id: 1, name: "Demo Customer", email: "customer@example.test", role: "customer",
  avatar_url: null, is_active: true, is_banned: false, email_verified: true,
  phone_verified: false, last_login_at: null, created_at: null,
};
const tokens = { access_token: "demo-access", refresh_token: "demo-refresh", token_type: "bearer", user };

test.afterEach(() => { setSessionTokens(null, null); });

test("demo login sends only the role and installs normal session tokens", async () => {
  for (const role of ["customer", "provider", "admin"]) {
    apiClient.defaults.adapter = async (config) => {
      assert.equal(config.url, "/demo/login");
      assert.deepEqual(JSON.parse(config.data), { role });
      return { data: { success: true, message: "OK", data: tokens }, status: 200, statusText: "OK", headers: {}, config };
    };
    assert.deepEqual(await loginWithDemoRole(role), tokens);
    assert.equal(getAccessToken(), "demo-access");
  }
});

test("failed demo login does not install tokens", async () => {
  setSessionTokens("old-access", "old-refresh");
  apiClient.defaults.adapter = async (config) => ({
    data: { success: false, message: "Unavailable", data: null }, status: 200, statusText: "OK", headers: {}, config,
  });
  await assert.rejects(loginWithDemoRole("customer"), /Unavailable/);
  assert.equal(getAccessToken(), "old-access");
});

test("demo login 401 never refreshes or retries a previous session", async () => {
  setSessionTokens("old-access", "old-refresh");
  const requests = [];
  apiClient.defaults.adapter = async (config) => {
    requests.push(config.url);
    throw new axios.AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, {
      status: 401, statusText: "Unauthorized", headers: {}, config, data: {},
    });
  };
  await assert.rejects(loginWithDemoRole("admin"), /Unauthorized/);
  assert.deepEqual(requests, ["/demo/login"]);
  assert.equal(getAccessToken(), "old-access");
});
