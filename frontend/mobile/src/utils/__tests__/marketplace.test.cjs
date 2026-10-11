const test = require("node:test");
const assert = require("node:assert/strict");

const {
  calculateMarketplaceEstimate,
  getMarketplaceBreakdown,
} = require("../../../.test-build/utils/marketplace.js");

test("calculates the fixed Sandbox marketplace estimate", () => {
  assert.deepEqual(calculateMarketplaceEstimate(1000), {
    total: 1000,
    platformCommission: 100,
    providerShare: 900,
    iyzicoFee: 43.15,
    taxAmount: 20,
    estimatedProviderIncome: 836.85,
    providerPayout: null,
    vatRate: 0.2,
    isEstimated: true,
    feeIsEstimated: true,
  });
});

test("rejects missing or non-positive amounts", () => {
  assert.equal(calculateMarketplaceEstimate(null), null);
  assert.equal(calculateMarketplaceEstimate(0), null);
  assert.equal(calculateMarketplaceEstimate("not-a-number"), null);
});

test("calculates the provider estimate from visit fee plus service amount", () => {
  const breakdown = calculateMarketplaceEstimate(22 + 230);

  assert.equal(breakdown.total, 252);
  assert.equal(breakdown.platformCommission, 25.2);
  assert.equal(breakdown.iyzicoFee, 11.06);
  assert.equal(breakdown.taxAmount, 5.04);
  assert.equal(breakdown.estimatedProviderIncome, 210.7);
});

test("prefers authoritative settlement values after capture", () => {
  const breakdown = getMarketplaceBreakdown({
    amount: 1000,
    settlement: {
      platform_commission_amount: 100,
      provider_share_amount: 900,
      provider_payout_amount: 899.5,
      iyzico_commission_fee: 43.15,
      status: "pending",
    },
  });

  assert.equal(breakdown.platformCommission, 100);
  assert.equal(breakdown.providerShare, 900);
  assert.equal(breakdown.providerPayout, 899.5);
  assert.equal(breakdown.iyzicoFee, 43.15);
  assert.equal(breakdown.isEstimated, false);
  assert.equal(breakdown.feeIsEstimated, false);
});
