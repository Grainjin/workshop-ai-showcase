import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";

import { PrimaryButton } from "./PrimaryButton";
import { SecondaryButton } from "./SecondaryButton";
import { TextField } from "./TextField";
import { colors, radius, spacing } from "../theme/theme";

export function ActionReasonModal({
  amount,
  amountLabel = "Amount (optional)",
  amountPlaceholder = "Leave blank for the full amount",
  confirmLabel,
  onCancel,
  onChangeAmount,
  onChangeReason,
  onConfirm,
  reason,
  reasonLabel = "Reason",
  title,
  error,
}: {
  amount?: string;
  amountLabel?: string;
  amountPlaceholder?: string;
  confirmLabel: string;
  onCancel: () => void;
  onChangeAmount?: (value: string) => void;
  onChangeReason: (value: string) => void;
  onConfirm: () => void;
  reason: string;
  reasonLabel?: string;
  title: string;
  error?: string;
}) {
  return (
    <Modal animationType="fade" onRequestClose={onCancel} transparent visible>
      <View style={styles.overlay}>
        <View style={styles.card}>
          <Text style={styles.title}>{title}</Text>
          <ScrollView contentContainerStyle={styles.content}>
            {onChangeAmount ? (
              <TextField
                keyboardType="decimal-pad"
                label={amountLabel}
                onChangeText={onChangeAmount}
                placeholder={amountPlaceholder}
                value={amount || ""}
              />
            ) : null}
            <TextField
              label={reasonLabel}
              multiline
              numberOfLines={4}
              onChangeText={onChangeReason}
              placeholder="Enter a reason"
              value={reason}
            />
            {error ? <Text style={styles.error}>{error}</Text> : null}
          </ScrollView>
          <View style={styles.actions}>
            <SecondaryButton label="Cancel" onPress={onCancel} />
            <PrimaryButton label={confirmLabel} onPress={onConfirm} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.42)",
    flex: 1,
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.background,
    borderRadius: radius.md,
    maxHeight: "80%",
    padding: spacing.lg,
    width: "100%",
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
  },
  content: {
    gap: spacing.sm,
    paddingVertical: spacing.md,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "flex-end",
  },
  error: {
    color: colors.danger,
    fontSize: 13,
  },
});
