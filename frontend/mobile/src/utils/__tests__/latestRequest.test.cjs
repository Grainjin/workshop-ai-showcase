const assert = require("node:assert/strict");
const test = require("node:test");

const {
  createLatestRequestGuard,
} = require("../../../.test-build/utils/latestRequest.js");

test("only the newest overlapping request may update the selected booking", () => {
  const guard = createLatestRequestGuard();
  const first = guard.begin();
  const second = guard.begin();

  assert.equal(guard.isLatest(first), false);
  assert.equal(guard.isLatest(second), true);
});

test("closing the modal invalidates the request still in flight", () => {
  const guard = createLatestRequestGuard();
  const request = guard.begin();
  guard.invalidate();

  assert.equal(guard.isLatest(request), false);
});
