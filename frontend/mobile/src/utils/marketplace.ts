import type { PaymentSummary } from "../types/booking";

/**
 * Fixed Sandbox display assumptions. The authoritative values after payment
 * come from the iyzico transaction response stored in the settlement.
 */
export const PLATFORM_COMMISSION_RATE = 0.1;
export const IYZICO_FEE_RATE = 0.0429;
export const IYZICO_FIXED_FEE = 0.25;
export const TURKEY_VAT_RATE = 0.2;

export type MarketplaceBreakdown = {
  total: number;
  platformCommission: number;
  providerShare: number;
  iyzicoFee: number;
  taxAmount: number;
  estimatedProviderIncome: number;
  providerPayout: number | null;
  vatRate: number;
  isEstimated: boolean;
  feeIsEstimated: boolean;
};

function roundMoney(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function calculateMarketplaceEstimate(
  amount: number | string | null | undefined,
): MarketplaceBreakdown | null {
  const total = Number(amount);
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  const platformCommission = roundMoney(total * PLATFORM_COMMISSION_RATE);
  const iyzicoFee = roundMoney(total * IYZICO_FEE_RATE + IYZICO_FIXED_FEE);
  // This is a simple display estimate for the platform VAT burden. It is
  // deliberately calculated from the platform commission, rather than
  // pretending that the provider's personal tax situation is known.
  const taxAmount = roundMoney(platformCommission * TURKEY_VAT_RATE);
  return {
    total: roundMoney(total),
    platformCommission,
    providerShare: roundMoney(total - platformCommission),
    iyzicoFee,
    taxAmount,
    estimatedProviderIncome: roundMoney(
      total - platformCommission - iyzicoFee - taxAmount,
    ),
    providerPayout: null,
    vatRate: TURKEY_VAT_RATE,
    isEstimated: true,
    feeIsEstimated: true,
  };
}

export function getMarketplaceBreakdown(
  payment?: PaymentSummary | null,
  fallbackAmount?: number | string | null,
): MarketplaceBreakdown | null {
  const estimate = calculateMarketplaceEstimate(payment?.amount ?? fallbackAmount);
  if (!estimate) {
    return null;
  }

  const settlement = payment?.settlement;
  if (!settlement) {
    return estimate;
  }

  return {
    ...estimate,
    platformCommission: Number(settlement.platform_commission_amount),
    providerShare: Number(settlement.provider_share_amount),
    taxAmount: estimate.taxAmount,
    estimatedProviderIncome: estimate.estimatedProviderIncome,
    providerPayout:
      settlement.provider_payout_amount == null
        ? null
        : Number(settlement.provider_payout_amount),
    iyzicoFee:
      settlement.iyzico_commission_fee == null
        ? estimate.iyzicoFee
        : Number(settlement.iyzico_commission_fee),
    isEstimated: false,
    feeIsEstimated: settlement.iyzico_commission_fee == null,
  };
}
