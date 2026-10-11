const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildReferencePricePresentation,
  resolveBookingReferenceDetail,
  shouldShowCustomerReferencePrice,
} = require("../../../.test-build/utils/referencePrice.js");

const history = {
  has_history: true,
  minimum: 900,
  maximum: 1100,
  currency: "TRY",
  sample_count: 3,
};

const noHistory = {
  has_history: false,
  minimum: null,
  maximum: null,
  currency: "TRY",
  sample_count: 0,
};

test("provider receives a non-binding recommendation presentation", () => {
  assert.deepEqual(buildReferencePricePresentation(history, "provider"), {
    label: "Recommended price range",
    value: "₺900–₺1,100",
  });
});

test("provider receives no invented value without history", () => {
  assert.deepEqual(buildReferencePricePresentation(noHistory, "provider"), {
    label: "Recommended price range",
    value: null,
  });
});

test("customer receives the fixed historical reference presentation", () => {
  assert.deepEqual(buildReferencePricePresentation(history, "customer"), {
    label: "Typical range for similar jobs",
    value: "₺900–₺1,100",
  });
});

test("customer receives the fixed no-history fallback", () => {
  assert.deepEqual(buildReferencePricePresentation(noHistory, "customer"), {
    label: "Typical range for similar jobs",
    value: "No historical data for similar jobs",
  });
});

test("presentation never returns input or validation behavior", () => {
  const presentation = buildReferencePricePresentation(history, "provider");
  assert.deepEqual(Object.keys(presentation).sort(), ["label", "value"]);
  assert.equal("inputValue" in presentation, false);
  assert.equal("validation" in presentation, false);
});

test("customer reference follows visible quote data rather than status alone", () => {
  assert.equal(shouldShowCustomerReferencePrice({ status: "quoted", quote_amount: 1000 }), true);
  assert.equal(shouldShowCustomerReferencePrice({ status: "final_quote_sent", final_quote_amount: 1200 }), true);
  assert.equal(shouldShowCustomerReferencePrice({ status: "refunding", quote_amount: 1000 }), true);
  assert.equal(shouldShowCustomerReferencePrice({ status: "pending", last_declined_quote: { quote_amount: 1000 } }), true);
  assert.equal(shouldShowCustomerReferencePrice({ status: "pending" }), false);
});

test("action responses are refreshed from the shared detail endpoint", async () => {
  const actionBooking = { id: 12, status: "quoted" };
  const detailBooking = { ...actionBooking, reference_price_range: history };
  const resolved = await resolveBookingReferenceDetail(
    actionBooking,
    async (bookingId) => {
      assert.equal(bookingId, 12);
      return detailBooking;
    },
  );
  assert.equal(resolved, detailBooking);
});

test("detail refresh failure preserves the available booking", async () => {
  const actionBooking = { id: 12, status: "quoted" };
  const resolved = await resolveBookingReferenceDetail(actionBooking, async () => {
    throw new Error("offline");
  });
  assert.equal(resolved, actionBooking);
});
