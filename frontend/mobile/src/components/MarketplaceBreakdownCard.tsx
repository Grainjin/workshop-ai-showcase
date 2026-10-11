import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { PaymentHistoryEntry, PaymentSummary } from "../types/booking";
import { getMarketplaceBreakdown } from "../utils/marketplace";
import { formatMoney } from "../utils/money";

export function MarketplaceBreakdownCard({
  amount,
  estimateOnly = false,
  payment,
  serviceAmount,
  serviceAmountLabel = "Expected service amount",
  visitFeeAmount,
  title = "Marketplace split",
}: {
  amount?: number | string | null;
  estimateOnly?: boolean;
  payment?: PaymentSummary | PaymentHistoryEntry | null;
  serviceAmount?: number | string | null;
  serviceAmountLabel?: string;
  visitFeeAmount?: number | string | null;
  title?: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const breakdown = getMarketplaceBreakdown(estimateOnly ? null : payment, amount);
  if (!breakdown) {
    return null;
  }

  const settlement = estimateOnly ? null : payment?.settlement;
  const providerIncome = breakdown.providerPayout ?? breakdown.estimatedProviderIncome;
  const totalDeductions = Math.max(0, breakdown.total - providerIncome);
  const payoutLabel = breakdown.providerPayout != null
    ? "Expected settlement from iyzico"
    : "Expected payout (estimate)";

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{title}</Text>
      {visitFeeAmount != null ? <Row label="Visit fee" value={formatMoney(visitFeeAmount)} /> : null}
      {serviceAmount != null ? <Row label={serviceAmountLabel} value={formatMoney(serviceAmount)} /> : null}
      {visitFeeAmount != null || serviceAmount != null ? (
        <Row label="Estimated customer total" value={formatMoney(breakdown.total)} />
      ) : null}
      <View style={styles.separator} />
      <Row label="Total deductions" value={formatMoney(totalDeductions)} emphasized />
      <Row label="Expected provider income" value={formatMoney(providerIncome)} emphasized />
      <Pressable
        accessibilityLabel={isExpanded ? "Hide fee details" : "View fee details"}
        accessibilityRole="button"
        onPress={() => setIsExpanded((expanded) => !expanded)}
        style={styles.detailsToggle}
      >
        <Text style={styles.detailsToggleText}>
          {isExpanded ? "Hide fee details" : "View fee details"}
        </Text>
        <Text style={styles.detailsToggleIcon}>{isExpanded ? "−" : "+"}</Text>
      </Pressable>
      {isExpanded ? (
        <View style={styles.details}>
          <Row label="Platform commission" value={formatMoney(breakdown.platformCommission)} />
          <Row label="Provider share" value={formatMoney(breakdown.providerShare)} />
          <Row
            label={`iyzico fee${breakdown.feeIsEstimated ? " (estimate)" : ""}`}
            value={formatMoney(breakdown.iyzicoFee)}
          />
          <Row label="VAT estimate" value={formatMoney(breakdown.taxAmount)} />
          <Row label={payoutLabel} value={formatMoney(providerIncome)} />
        </View>
      ) : null}
      {settlement ? (
        <Row label="Settlement" value={formatSettlementStatus(settlement.status)} />
      ) : (
        <Text style={styles.note}>Estimate until the payment is captured.</Text>
      )}
      <Text style={styles.note}>
        Tax and payment fees are fixed Sandbox estimates; the final settlement comes from iyzico.
      </Text>
      {settlement?.failure_message ? (
        <Text style={styles.error}>{settlement.failure_message}</Text>
      ) : null}
      {settlement?.provider_recovery_amount != null ? (
        <Row
          label="Recovery"
          value={`${formatMoney(settlement.provider_recovery_amount)} · ${settlement.recovery_status || "Pending"}`}
        />
      ) : null}
    </View>
  );
}

function Row({
  emphasized = false,
  label,
  value,
}: {
  emphasized?: boolean;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={[styles.label, emphasized ? styles.emphasized : null]}>{label}</Text>
      <Text style={[styles.value, emphasized ? styles.emphasized : null]}>{value}</Text>
    </View>
  );
}

function formatSettlementStatus(status: string) {
  return status.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

const styles = StyleSheet.create({
  card: {
    gap: spacing.xs,
    borderRadius: radius.sm,
    backgroundColor: colors.background,
    padding: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  separator: {
    borderTopColor: colors.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginVertical: spacing.xs,
  },
  detailsToggle: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  detailsToggleText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  detailsToggleIcon: {
    color: colors.primary,
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 18,
  },
  details: {
    borderTopColor: colors.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    gap: spacing.xs,
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
  },
  label: {
    color: colors.mutedText,
    fontSize: 13,
  },
  value: {
    color: colors.text,
    flexShrink: 1,
    fontSize: 13,
    fontWeight: "700",
    textAlign: "right",
  },
  emphasized: {
    color: colors.text,
    fontWeight: "800",
  },
  note: {
    color: colors.mutedText,
    fontSize: 12,
  },
  error: {
    color: colors.danger,
    fontSize: 13,
  },
});
