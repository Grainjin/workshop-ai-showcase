const assert = require("node:assert/strict");
const test = require("node:test");

const { isValidTurkishIban } = require("../../../.test-build/iban.js");

test("accepts the seeded Turkish Sandbox IBAN", () => {
  assert.equal(isValidTurkishIban("TR180006200119000006672315"), true);
});

test("rejects an invalid Turkish IBAN checksum", () => {
  assert.equal(isValidTurkishIban("TR000000000000000000000000"), false);
});
