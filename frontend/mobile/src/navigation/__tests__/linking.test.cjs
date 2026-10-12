const assert = require("node:assert/strict");
const { readFileSync, existsSync } = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { before, test } = require("node:test");
const ts = require("typescript");

let realParser;
before(async () => {
  const core = path.dirname(require.resolve("@react-navigation/core/package.json"));
  ({ getStateFromPath: realParser } = await import(pathToFileURL(
    path.join(core, "lib/module/getStateFromPath.js"),
  )));
});

// Execute the application's actual linking configuration without mounting its
// native screens. Success tests use the installed parser; refusal tests use a
// sentinel because invoking the affected decoder is precisely what we forbid.
function applicationLinking(parser) {
  const filename = path.join(__dirname, "../AppNavigator.tsx");
  const source = ts.createSourceFile(filename, readFileSync(filename, "utf8"),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declaration = source.statements.filter(ts.isVariableStatement)
    .flatMap(statement => [...statement.declarationList.declarations])
    .find(item => item.name.getText(source) === "linking");
  assert.ok(declaration, "Application must expose its navigation linking configuration");
  const compiled = path.join(__dirname, "../../../.test-build/navigation/guardedPathParser.js");
  const createGuardedPathParser = existsSync(compiled)
    ? require(compiled).createGuardedPathParser : undefined;
  return new Function("getStateFromPath", "createGuardedPathParser",
    `return (${declaration.initializer.getText(source)});`)(parser, createGuardedPathParser);
}

function parse(linking, raw, options = linking.config, parser = realParser) {
  return (linking.getStateFromPath ?? parser)(raw, options);
}

// Break caught: removing/bypassing the guard exposes malformed input to parsing.
for (const malformed of [
  "/payment-result?x=%", "/payment-result?x=%ZZ",
  "/payment-result?x=%E0%A4", "/payment-result?x=%FF",
  "/payment-result?%FF=value", "/payment-result?%E0%A4=value",
  "/payment-result?%=value", "/payment-result?%ZZ=value",
  "/payment-result?x=ok&x=%FF", "/payment-result?x=" + "%FF".repeat(64),
  "/pay%FFment-result?x=ok", "/payment-result?x=%C0%AF",
  "/payment-result?x=%ED%A0%80", "/payment-result?x=%F4%90%80%80",
]) {
  test(`refuses malformed encoding before parsing: ${malformed.slice(0, 70)}`, () => {
    const forbidden = () => assert.fail("Malformed input reached navigation parser");
    const linking = applicationLinking(forbidden);
    assert.equal(parse(linking, malformed, linking.config, forbidden), undefined);
  });
}

for (const raw of [undefined, null, 42, {}, ["/payment-result"]]) {
  test(`refuses non-string input before parsing: ${JSON.stringify(raw)}`, () => {
    const forbidden = () => assert.fail("Non-string input reached navigation parser");
    const linking = applicationLinking(forbidden);
    assert.equal(parse(linking, raw, linking.config, forbidden), undefined);
  });
}

test("refuses raw input above 4096 UTF-16 code units before parsing", () => {
  const forbidden = () => assert.fail("Over-cap input reached navigation parser");
  const linking = applicationLinking(forbidden);
  const prefix = "/payment-result?x=";
  assert.equal(parse(linking, prefix + "a".repeat(4097 - prefix.length),
    linking.config, forbidden), undefined);
  assert.equal(parse(linking, prefix + "😀".repeat(2040),
    linking.config, forbidden), undefined);
});

// Break caught: passing decoded/rebuilt strings or copied options changes the
// parser contract; valid caller options must be passed through by identity.
test("forwards original raw input and original options unchanged at the cap", () => {
  const options = { screens: { PaymentResult: "payment-result" } };
  const prefix = "/payment-result?x=%26+%2B&padding=";
  const raw = prefix + "a".repeat(4096 - prefix.length);
  const sentinel = { routes: [{ name: "PaymentResult" }] };
  const parser = (receivedRaw, receivedOptions) => {
    assert.equal(receivedRaw, raw);
    assert.equal(receivedOptions, options);
    return sentinel;
  };
  assert.equal(parse(applicationLinking(parser), raw, options, parser), sentinel);
});

test("forwards omitted options without inventing configuration", () => {
  const parser = (raw, options) => {
    assert.equal(raw, "/payment-result");
    assert.equal(options, undefined);
    return undefined;
  };
  const linking = applicationLinking(parser);
  assert.equal((linking.getStateFromPath ?? parser)("/payment-result"), undefined);
});

// Break caught: changed payment route or normalizing/decode-and-forward changes
// real query behavior. Literal expected values are independently hand-derived.
for (const [raw, params] of [
  ["/payment-result", undefined],
  ["/payment-result?booking_id=301&status=success&payment_id=72",
    { booking_id: "301", status: "success", payment_id: "72" }],
  ["/payment-result?booking_id=301&status=failure", { booking_id: "301", status: "failure" }],
  ["/payment-result?note=%E4%BD%A0%E5%A5%BD%20%F0%9F%98%80", { note: "你好 😀" }],
  ["/payment-result?note=a%26b%3Dc%2Fd%3Fz%23f&plus=%2B&space=a+b",
    { note: "a&b=c/d?z#f", plus: "+", space: "a b" }],
  ["/payment-result?x=first&x=second&empty=&flag&%E9%94%AE=%E5%80%BC",
    { x: ["first", "second"], empty: "", flag: null, "键": "值" }],
  ["/payment-result?x=%25FF", { x: "%FF" }],
]) {
  test(`keeps real payment parser semantics: ${raw}`, () => {
    const linking = applicationLinking(realParser);
    const result = parse(linking, raw);
    assert.ok(result);
    assert.equal(result.routes[0].name, "PaymentResult");
    assert.equal(result.routes[0].path, raw);
    assert.deepEqual(result.routes[0].params, params);
  });
}

test("valid payment URL at the cap is accepted by the real parser", () => {
  const prefix = "/payment-result?note=";
  const raw = prefix + "😀".repeat(2037) + "a".repeat(4096 - prefix.length - 4074);
  assert.equal(raw.length, 4096);
  const result = parse(applicationLinking(realParser), raw);
  assert.equal(result.routes[0].name, "PaymentResult");
  assert.equal(result.routes[0].params.note.length, 4096 - prefix.length);
});
