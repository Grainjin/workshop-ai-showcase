const test = require("node:test");
const assert = require("node:assert/strict");
const { buildBookingQuoteBody } = require("../../../.test-build/utils/bookingQuoteUpload.js");

test("quotes without files retain the JSON contract", async () => {
  const fields = { quote_amount: 250, quote_message: null, visit_fee_amount: 40 };
  const body = await buildBookingQuoteBody(fields, [], () => { throw Error("No file upload expected"); });
  assert.equal(body, fields);
});

test("visit and final quotes send every selected file in multipart quote_files", async () => {
  const files = [{ uri: "file:a", fileName: "same.png" }, { uri: "file:b", fileName: "same.png" }];
  for (const fields of [
    { quote_amount: 250, quote_message: "Visit", expected_service_amount: 250, visit_fee_amount: 40 },
    { quote_amount: 275, quote_message: null },
  ]) {
    const appended = [];
    const body = await buildBookingQuoteBody(fields, files, async (form, field, file) => {
      assert.ok(form instanceof FormData);
      appended.push([field, file.uri]);
      form.append(field, new Blob([file.uri], { type: "image/png" }), file.fileName);
    });
    assert.equal(body.get("quote_amount"), String(fields.quote_amount));
    assert.equal(body.get("visit_fee_amount"), fields.visit_fee_amount == null ? null : String(fields.visit_fee_amount));
    assert.equal(body.getAll("quote_files").length, 2);
    assert.deepEqual(appended, [["quote_files", "file:a"], ["quote_files", "file:b"]]);
    assert.equal(body.getAll("proof_files").length, 0);
  }
});
