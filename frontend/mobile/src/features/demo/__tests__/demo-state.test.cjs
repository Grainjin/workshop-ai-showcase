const assert = require("node:assert/strict");
const test = require("node:test");
const {
  createDemoLoginState,
  getDemoRoleButtons,
  reduceDemoLogin,
} = require("../../../../.test-build/features/demo/demo-state.js");

test("disabled demo mode exposes no role buttons", () => {
  assert.deepEqual(getDemoRoleButtons(false, createDemoLoginState()), []);
});

test("demo choices offer Customer, Provider, Admin in order with accessible purposes", () => {
  const buttons = getDemoRoleButtons(true, createDemoLoginState());
  assert.deepEqual(buttons.map(({ role, label }) => [role, label]), [
    ["customer", "Customer"], ["provider", "Provider"], ["admin", "Admin"],
  ]);
  for (const button of buttons) {
    assert.ok(button.purpose.length > 0);
    assert.match(button.accessibilityLabel, new RegExp(button.label));
    assert.match(button.accessibilityLabel, /demo/i);
    assert.equal(button.disabled, false);
    assert.equal(button.isLoading, false);
  }
});

test("only the selected role loads while every role is disabled", () => {
  for (const role of ["customer", "provider", "admin"]) {
    const state = reduceDemoLogin(createDemoLoginState(), { type: "start", role });
    const buttons = getDemoRoleButtons(true, state);
    assert.deepEqual(buttons.filter((button) => button.isLoading).map((button) => button.role), [role]);
    assert.ok(buttons.every((button) => button.disabled));
    assert.deepEqual(reduceDemoLogin(state, { type: "start", role: "admin" }), state);
  }
});

test("failure resets loading and shows a safe message without backend details", () => {
  const loading = reduceDemoLogin(createDemoLoginState(), { type: "start", role: "admin" });
  const failed = reduceDemoLogin(loading, { type: "failure" });
  assert.equal(failed.pendingRole, null);
  assert.match(failed.errorMessage, /try again/i);
  assert.ok(getDemoRoleButtons(true, failed).every((button) => !button.disabled && !button.isLoading));
  const retry = reduceDemoLogin(failed, { type: "start", role: "provider" });
  assert.equal(retry.errorMessage, "");
  assert.equal(retry.pendingRole, "provider");
});

test("successful sign-in clears error and loading", () => {
  const loading = reduceDemoLogin(createDemoLoginState(), { type: "start", role: "customer" });
  assert.deepEqual(reduceDemoLogin(loading, { type: "success" }), {
    pendingRole: null, errorMessage: "",
  });
});
