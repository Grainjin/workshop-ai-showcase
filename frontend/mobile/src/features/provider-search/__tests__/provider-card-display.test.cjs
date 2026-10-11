const assert = require("node:assert/strict");
const test = require("node:test");

const {
  formatProviderDistance,
  getProviderCardImageUrl,
  getProviderCardStatus,
} = require("../../../../.test-build/provider-card-display.js");

test("provider card prefers the account avatar over portfolio media", () => {
  assert.equal(
    getProviderCardImageUrl({
      avatarUrl: "/uploads/avatar.png",
      portfolioImageUrl: "/uploads/work.png",
    }),
    "/uploads/avatar.png",
  );
});

test("provider card falls back to portfolio media while avatar is unavailable", () => {
  assert.equal(
    getProviderCardImageUrl({
      avatarUrl: null,
      portfolioImageUrl: "/uploads/work.png",
    }),
    "/uploads/work.png",
  );
});

test("provider card uses opening state when the search API supplies it", () => {
  assert.deepEqual(getProviderCardStatus({ isOpen: false, isOnline: true }), {
    label: "Closed",
    tone: "inactive",
  });
});

test("recommendation cards still fall back to online presence", () => {
  assert.deepEqual(getProviderCardStatus({ isOnline: true }), {
    label: "Online",
    tone: "active",
  });
});

test("provider card formats API-provided distance for display", () => {
  assert.equal(formatProviderDistance(2.46), "2.5 km away");
  assert.equal(formatProviderDistance(null), null);
});
