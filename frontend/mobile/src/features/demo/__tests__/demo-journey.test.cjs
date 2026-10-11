const assert = require("node:assert/strict");
const test = require("node:test");
const Module = require("node:module");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const web = require("react-native-web");
const build = "../../../../.test-build/";

function load(enabled, bookingStatus = "visit_paid") {
  const original = Module._load;
  const state = [];
  const chatState = [];
  let cursor = 0;
  Module._load = function(request, parent, ...args) {
    if (request === "react-native") return { ...web, Modal: web.View, Alert: { alert() {} } };
    if (request.endsWith("config/env")) return { DEMO_MODE: enabled, API_BASE_URL: "http://localhost" };
    if (request === "@react-navigation/native") return { useFocusEffect() {} };
    if (request === "expo-image-picker") return {};
    if (request === "lucide-react-native") return new Proxy({}, { get: () => () => null });
    if (request.endsWith("/AuthContext")) return { useAuth: () => ({ user: { id: 7, role: "provider" } }) };
    if (request.endsWith("/RealtimeContext")) return { useRealtime: () => ({ markChatRoomRead() {} }) };
    if (request.endsWith("/useConfirmation")) return { useConfirmation: () => ({ confirmationModal: null }) };
    // Keep the real chat handlers, API and proof modal; unrelated native UI needs a Node stand-in.
    if (parent?.filename.endsWith("ChatRoomScreen.js") && request.startsWith("../components/") &&
        !request.endsWith("/ProviderBookingDetailModal")) {
      return new Proxy({}, { get: (_, key) => key === "createDefaultBookingRequestForm" ? () => ({}) : () => null });
    }
    if (request === "react" && parent?.filename.endsWith("ChatRoomScreen.js")) return {
      ...React, useRef: value => ({ current: value }), useCallback: fn => fn,
      useEffect() {}, useLayoutEffect() {}, useMemo: fn => fn(),
      useState: initial => {
        const i = cursor++;
        if (!(i in chatState)) chatState[i] = i === 5 ? { id: 12, status: bookingStatus } : initial;
        return [chatState[i], value => { chatState[i] = typeof value === "function" ? value(chatState[i]) : value; }];
      },
    };
    if (request === "react" && parent?.filename.endsWith("ProviderProfileGateContext.js")) return {
      ...React,
      useState: (initial) => { const i = cursor++; if (!(i in state)) state[i] = initial;
        return [state[i], value => { state[i] = typeof value === "function" ? value(state[i]) : value; }]; },
      useCallback: fn => fn, useEffect: () => {}, useMemo: fn => fn(),
    };
    if (request === "react" && parent?.filename.endsWith("ProviderBookingsScreen.js")) return {
      ...React, useRef: value => ({ current: value }), useCallback: fn => fn, useEffect() {},
      useState: initial => {
        const i = cursor++;
        return [i === 2 ? { id: 12, status: bookingStatus } : initial, () => {}];
      },
    };
    // Other detail sections have their own tests; render the real proof controls and buttons.
    if (parent?.filename.endsWith("ProviderBookingDetailModal.js") &&
        /^\.\/(Booking|Marketplace|QuoteAttachmentPicker|ReferencePriceRange|TextField)/.test(request)) {
      return new Proxy({}, { get: () => () => null });
    }
    return original.call(this, request, parent, ...args);
  };
  try {
    for (const name of ["api/provider", "api/marketplace", "context/ProviderProfileGateContext", "components/ProviderBookingDetailModal", "screens/provider/ProviderBookingsScreen", "screens/ChatRoomScreen"])
      delete require.cache[require.resolve(build + name + ".js")];
    const api = require(build + "api/provider.js");
    const { apiClient } = require(build + "api/client.js");
    const { ProviderBookingDetailModal } = require(build + "components/ProviderBookingDetailModal.js");
    const { ProviderProfileGateProvider } = require(build + "context/ProviderProfileGateContext.js");
    const { ProviderBookingsScreen } = require(build + "screens/provider/ProviderBookingsScreen.js");
    const { ChatRoomScreen } = require(build + "screens/ChatRoomScreen.js");
    return { api, apiClient, ProviderBookingDetailModal,
      chat: () => { cursor = 0; return ChatRoomScreen({ navigation: {}, route: { params: { chatRoomId: 1 } } }); },
      screen: () => { cursor = 0; return ProviderBookingsScreen(); },
      gate: () => { cursor = 0; return ProviderProfileGateProvider({ children: null }).props.value; } };
  } finally { Module._load = original; }
}

function detailProps(node, detail) {
  if (!node || typeof node !== "object") return null;
  if (node.type === detail) return node.props;
  for (const child of React.Children.toArray(node.props?.children)) {
    const result = detailProps(child, detail);
    if (result) return result;
  }
  return null;
}

function buttonProps(node, label) {
  if (!node || typeof node !== "object") return null;
  if (node.props?.label === label && typeof node.props.onPress === "function") return node.props;
  for (const child of React.Children.toArray(node.props?.children)) {
    const result = buttonProps(child, label);
    if (result) return result;
  }
  return null;
}

test("actual chat preset buttons send empty-proof demo requests while normal chat requires uploads", async () => {
  for (const enabled of [true, false]) {
    for (const [status, action, label] of [
      ["visit_paid", "onStartVisit", "Start visit with demo proof"],
      ["service_paid", "onComplete", "Complete with demo proof"],
    ]) {
      const { apiClient, chat, ProviderBookingDetailModal } = load(enabled, status);
      const writes = [];
      apiClient.defaults.adapter = async config => {
        if (config.method === "put") {
          writes.push(config.url);
          assert.equal(config.data, undefined);
        }
        return { status: 200, statusText: "OK", headers: {}, config,
          data: { success: true, data: { messages: [], items: [], booking: { id: 12 } } } };
      };
      const props = detailProps(chat(), ProviderBookingDetailModal);
      assert.ok(props, "Chat must render its real booking detail modal");
      const html = renderToStaticMarkup(React.createElement(ProviderBookingDetailModal, props));
      if (enabled) {
        assert.ok(html.includes(label));
        assert.doesNotMatch(html, /Add proof/);
      } else assert.match(html, /Add proof/);
      const button = buttonProps(ProviderBookingDetailModal(props), enabled ? label :
        action === "onStartVisit" ? "Start visit" : "Mark complete");
      assert.ok(button, "Real modal must wire the visible fulfillment button to the chat handler");
      button.onPress();
      await new Promise(resolve => setImmediate(resolve));
      assert.deepEqual(writes, enabled ? [action === "onStartVisit"
        ? "/provider/demo/bookings/12/start-visit" : "/provider/demo/bookings/12/complete"] : []);
      const next = detailProps(chat(), ProviderBookingDetailModal);
      if (enabled) {
        assert.equal(next.actionError, "");
        assert.equal(next.booking, null, "Successful preset action closes the chat booking modal");
      }
      else assert.match(next.actionError, /Add at least one photo or video/);
    }
  }
});

test("real provider gate accepts seeded API shape and keeps draft payout blocked", async () => {
  const { apiClient, gate } = load(true);
  let payoutStatus = "active";
  apiClient.defaults.adapter = async config => ({ status: 200, statusText: "OK", headers: {}, config,
    data: { success: true, message: "OK", data: config.url.endsWith("verification-status")
      ? { identity_status: "approved", qualification_status: "approved", identity_application_id: 1, qualification_application_id: null }
      : { submerchant: { id: 1, provider_profile_id: 1, submerchant_type: "PERSONAL", submerchant_external_id: "demo-provider-1",
          name: "Simulated demo payout account", email: "demo_provider_1@workshop.ai", gsm_number: "", address: "Public demo — no real payouts",
          iban: null, contact_name: null, contact_surname: null, identity_number: null, tax_office: null, tax_number: null,
          legal_company_title: null, currency: "TRY", status: payoutStatus, iyzico_error_code: null, iyzico_error_message: null,
          last_synced_at: null, created_at: "2026-10-11T00:00:00Z", updated_at: "2026-10-11T00:00:00Z" } } } });
  await gate().refreshProviderProfileStatus();
  assert.equal(gate().hasProviderProfile, true);
  assert.equal(gate().isProviderProfileRequired, false);
  assert.deepEqual(gate().incompleteProviderSteps, []);
  payoutStatus = "draft";
  await gate().refreshProviderProfileStatus();
  assert.equal(gate().isProviderProfileRequired, true);
  assert.deepEqual(gate().incompleteProviderSteps, ["payout"]);
});

test("actual booking screen allows preset fulfillment without picked files only in demo", async () => {
  function detailProps(node, detail) {
    if (!node || typeof node !== "object") return null;
    if (node.type === detail) return node.props;
    for (const child of React.Children.toArray(node.props?.children)) {
      const result = detailProps(child, detail);
      if (result) return result;
    }
    return null;
  }
  for (const enabled of [true, false]) {
    for (const [status, action] of [["visit_paid", "onStartVisit"], ["service_paid", "onComplete"]]) {
      const { apiClient, screen, ProviderBookingDetailModal } = load(enabled, status);
      const writes = [];
      apiClient.defaults.adapter = async config => {
        if (config.method === "put") writes.push(config.url);
        return { status: 200, statusText: "OK", headers: {}, config,
          data: { success: true, data: { items: [], booking: { id: 12 } } } };
      };
      const props = detailProps(screen(), ProviderBookingDetailModal);
      assert.ok(props, "Screen must render its real booking detail modal");
      await props[action]();
      assert.deepEqual(writes, enabled ? [action === "onStartVisit"
        ? "/provider/demo/bookings/12/start-visit" : "/provider/demo/bookings/12/complete"] : []);
    }
  }
});

test("demo proof API sends only the booking path, never visitor file URLs or bodies", async () => {
  const { api, apiClient } = load(true);
  const paths = [];
  apiClient.defaults.adapter = async config => {
    paths.push(config.url);
    assert.equal(config.data, undefined);
    return { status: 200, statusText: "OK", headers: {}, config, data: { success: true, data: { booking: { id: 12 } } } };
  };
  const previousFetch = global.fetch;
  global.fetch = async () => assert.fail("Demo proof must not read any client file or URL");
  try {
    await api.startProviderVisit(12, [{ uri: "https://attacker.test/proof.png" }]);
    await api.completeProviderBooking(12, [{ uri: "file:///private/proof.png" }]);
    assert.deepEqual(paths, ["/provider/demo/bookings/12/start-visit", "/provider/demo/bookings/12/complete"]);
  } finally { global.fetch = previousFetch; }
});

test("booking journey shows accessible preset actions and disclosure, normal mode retains uploads", () => {
  for (const enabled of [true, false]) {
    const { ProviderBookingDetailModal } = load(enabled);
    for (const [status, label] of [["visit_paid", "Start visit with demo proof"], ["service_paid", "Complete with demo proof"]]) {
      const html = renderToStaticMarkup(React.createElement(ProviderBookingDetailModal, {
        booking: { id: 12, status }, onClose() {}, onStartVisit() {}, onComplete() {}, onPickCompletionProof() {},
      }));
      assert.match(html, /role="button"/);
      if (enabled) {
        assert.ok(html.includes(label), html);
        assert.match(html, /server-selected simulated proof/);
        assert.doesNotMatch(html, /Add proof/);
      } else {
        assert.match(html, /Add proof/);
        assert.doesNotMatch(html, /server-selected simulated proof/);
      }
    }
  }
});
