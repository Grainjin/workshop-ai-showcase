const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");
const React = require("react");

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const settle = () => new Promise(resolve => setImmediate(resolve));
const provider = id => ({
  id, user_id: id + 10, business_name: `Demo provider ${id}`, bio: "Demo service",
  phone_number: "", address: "Demo address", service_province: "Istanbul", service_location_id: 132,
  latitude: 41, longitude: 29, tags: ["cleaning"], certificate_name: "", certificate_url: "",
  certificate_files: [], hourly_rate: 100, verification_status: "approved", verification_note: null,
  notes: null, is_online: false, first_portfolio_image_url: null, recommendation_score: 1,
  matched_tags: ["cleaning"], recommendation_reasons: [],
});
const district = {
  service_province: "Istanbul", service_location_id: 132,
  history_provider_tag: "cleaning", items: [provider(1), provider(23)],
};

// Execute the real screen and generation utility. Only native UI, hook scheduling,
// and the external API boundary need stand-ins in this Node regression.
function home() {
  const slots = [], effects = [], requests = [], profile = deferred();
  let cursor = 0, tree, focus, focused = true, writes = 0;
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  function effect(fn, deps) {
    const i = cursor++;
    if (!slots[i] || !same(slots[i].deps, deps)) {
      const previous = slots[i];
      slots[i] = { deps };
      effects.push(() => { previous?.cleanup?.(); slots[i].cleanup = fn(); });
    }
  }
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = { value: initial };
      return [slots[i].value, value => {
        writes++;
        slots[i].value = typeof value === "function" ? value(slots[i].value) : value;
      }];
    },
    useRef(value) {
      const i = cursor++;
      if (!(i in slots)) slots[i] = { current: value };
      return slots[i];
    },
    useCallback(fn, deps) {
      const i = cursor++;
      if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, fn };
      return slots[i].fn;
    },
    useEffect: effect,
  };
  const components = new Proxy({}, { get: (_, name) => name });
  const subscribe = () => () => {};
  function load(filename) {
    const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    const exports = {};
    vm.runInNewContext(code, { exports, require(name) {
      if (name === "react") return hooks;
      if (name === "react/jsx-runtime") return require(name);
      if (name === "react-native") return {
        ActivityIndicator: "ActivityIndicator", Pressable: "Pressable", Text: "Text",
        TextInput: "TextInput", View: "View", StyleSheet: { create: value => value },
      };
      if (name === "@react-navigation/native") return {
        useNavigation: () => ({}), useFocusEffect(fn) {
          if (focus?.fn !== fn) {
            const previous = focus;
            focus = { fn };
            effects.push(() => { previous?.cleanup?.(); if (focused) focus.cleanup = fn(); });
          }
        },
      };
      if (name.endsWith("api/customer")) return {
        getCustomerProfile: () => profile.promise,
        getCustomerHomeRecommendations(province, tag, location) {
          const request = { province, tag, location, ...deferred() };
          requests.push(request);
          return request.promise;
        },
        updateCustomerServiceProvince: async () => undefined,
      };
      if (name.endsWith("RealtimeContext")) return { useRealtime: () => ({ subscribe }) };
      if (name.endsWith("theme/theme")) return { colors: {}, radius: {}, spacing: {} };
      if (name.endsWith("providerTags")) return {
        DEFAULT_PROVIDER_TAG: "cleaning", PROVIDER_TAGS: ["cleaning"], getProviderTagLabel: v => v,
      };
      if (name.endsWith("utils/latestRequest")) return load(path.resolve(__dirname, "../../../utils/latestRequest.ts"));
      if (name.includes("components/") || name === "lucide-react-native") return components;
      throw new Error("Unexpected dependency " + name);
    } });
    return exports;
  }
  const { CustomerHomeScreen } = load(path.resolve(__dirname, "../CustomerHomeScreen.tsx"));
  function render() {
    cursor = 0;
    tree = CustomerHomeScreen();
    effects.splice(0).forEach(fn => fn());
    return tree;
  }
  function find(type, node = tree) {
    if (!node || typeof node !== "object") return [];
    return [...(node.type === type ? [node.props] : []),
      ...React.Children.toArray(node.props?.children).flatMap(child => find(type, child))];
  }
  render();
  return {
    profile, requests, render, find, get writes() { return writes; },
    blur() { focused = false; focus?.cleanup?.(); },
    refocus() { focused = true; focus.cleanup = focus.fn(); },
    unmount() { focus?.cleanup?.(); slots.forEach(slot => slot?.cleanup?.()); },
    ids() { render(); return find("ProviderRecommendationCard").map(props => props.provider.id); },
    loading() { render(); return find("ActivityIndicator").length > 0; },
  };
}

async function hydrate(screen) {
  screen.profile.resolve({ service_province: "Istanbul", service_location_id: 132 });
  await settle(); screen.render();
  assert.deepEqual(screen.requests.map(r => r.location), [undefined, 132]);
}

test("saved district survives an older province response arriving last", async () => {
  const screen = home(); await hydrate(screen);
  screen.requests[1].resolve(district); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
  screen.requests[0].resolve({
    service_province: "Istanbul", service_location_id: null,
    history_provider_tag: "plumbing", items: [provider(29)],
  }); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
  assert.equal(screen.loading(), false);
});

test("obsolete error and finally cannot clear district results or finish its loading", async () => {
  const screen = home(); await hydrate(screen);
  screen.requests[0].reject(new Error("obsolete")); await settle();
  assert.equal(screen.loading(), true);
  screen.requests[1].resolve(district); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
});

test("obsolete failure after district success cannot clear its cards", async () => {
  const screen = home(); await hydrate(screen);
  screen.requests[1].resolve(district); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
  screen.requests[0].reject(new Error("obsolete")); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
  assert.equal(screen.loading(), false);
});

for (const lifecycle of ["blur", "unmount"]) {
  test(`${lifecycle} prevents late success, error and loading writes`, async () => {
    for (const outcome of ["resolve", "reject"]) {
      const screen = home(); screen[lifecycle]();
      const before = screen.writes;
      screen.requests[0][outcome](outcome === "resolve" ? district : new Error("late")); await settle();
      assert.equal(screen.writes, before);
    }
  });
}

test("refocus refreshes and a current error finishes loading with an empty result", async () => {
  const screen = home(); await hydrate(screen);
  screen.requests[1].resolve(district); await settle();
  assert.deepEqual(screen.ids(), [1, 23]);
  screen.blur(); screen.refocus();
  assert.equal(screen.loading(), true);
  assert.equal(screen.requests[2].location, 132);
  screen.requests[2].reject(new Error("current")); await settle();
  assert.deepEqual(screen.ids(), []);
  assert.equal(screen.loading(), false);
  screen.unmount();
});
