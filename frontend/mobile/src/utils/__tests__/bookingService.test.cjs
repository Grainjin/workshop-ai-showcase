const test = require("node:test");
const assert = require("node:assert/strict");

const {
  getDefaultServiceCategory,
  isCanonicalServiceSelection,
} = require("../../../.test-build/utils/bookingService.js");

test("auto-selects the only canonical service value", () => {
  assert.equal(getDefaultServiceCategory(["plumbing"]), "plumbing");
});

test("requires an explicit selection when multiple services are enabled", () => {
  assert.equal(getDefaultServiceCategory(["plumbing", "cleaning"]), "");
});

test("accepts the exact canonical service value", () => {
  assert.equal(isCanonicalServiceSelection("plumbing", ["plumbing"]), true);
});

test("rejects a presentation label instead of normalizing it", () => {
  assert.equal(isCanonicalServiceSelection("Plumbing", ["plumbing"]), false);
});
