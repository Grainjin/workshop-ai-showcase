import { useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Star } from "lucide-react-native";

import { PrimaryButton } from "./PrimaryButton";
import { SecondaryButton } from "./SecondaryButton";
import { colors, radius, spacing } from "../theme/theme";
import type { BookingDetail } from "../types/booking";

type CustomerReviewModalProps = {
  booking: BookingDetail | null;
  errorMessage: string;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (rating: number, comment: string) => void;
};

export function CustomerReviewModal({
  booking,
  errorMessage,
  isSubmitting,
  onClose,
  onSubmit,
}: CustomerReviewModalProps) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (booking) {
      setRating(0);
      setComment("");
      setFormError("");
    }
  }, [booking?.id]);

  if (!booking) {
    return null;
  }

  function handleSubmit() {
    const trimmedComment = comment.trim();
    if (rating === 0) {
      setFormError("Select a rating.");
      return;
    }
    if (!trimmedComment) {
      setFormError("Enter a review.");
      return;
    }

    setFormError("");
    onSubmit(rating, trimmedComment);
  }

  return (
    <Modal animationType="fade" onRequestClose={onClose} transparent visible>
      <View style={styles.overlay}>
        <View style={styles.card}>
          <Text style={styles.title}>Rate this service</Text>
          <Text style={styles.providerName}>
            {booking.provider?.business_name || `Provider #${booking.provider_profile_id}`}
          </Text>
          <Text style={styles.label}>Rating</Text>
          <View style={styles.stars}>
            {Array.from({ length: 5 }, (_, index) => {
              const value = index + 1;
              const selected = value <= rating;
              return (
                <Pressable
                  accessibilityLabel={`${value} stars`}
                  accessibilityRole="button"
                  disabled={isSubmitting}
                  key={value}
                  onPress={() => {
                    setRating(value);
                    setFormError("");
                  }}
                  style={styles.starButton}
                >
                  <Star
                    color={selected ? colors.primary : colors.mutedText}
                    fill={selected ? colors.primary : "transparent"}
                    size={34}
                    strokeWidth={1.8}
                  />
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.ratingHint}>
            {rating > 0 ? `${rating} / 5` : "Tap a star to rate"}
          </Text>
          <Text style={styles.label}>Review</Text>
          <TextInput
            editable={!isSubmitting}
            multiline
            numberOfLines={5}
            onChangeText={(value) => {
              setComment(value);
              setFormError("");
            }}
            placeholder="Write a review"
            placeholderTextColor={colors.mutedText}
            style={styles.input}
            textAlignVertical="top"
            value={comment}
          />
          {formError || errorMessage ? (
            <Text style={styles.errorText}>{formError || errorMessage}</Text>
          ) : null}
          <View style={styles.actions}>
            <SecondaryButton disabled={isSubmitting} label="Not now" onPress={onClose} />
            <PrimaryButton
              disabled={isSubmitting}
              isLoading={isSubmitting}
              label="Submit review"
              onPress={handleSubmit}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(15, 23, 42, 0.45)",
    padding: spacing.lg,
  },
  card: {
    width: "100%",
    maxWidth: 520,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "800",
  },
  providerName: {
    color: colors.mutedText,
    fontSize: 14,
  },
  label: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
    marginTop: spacing.sm,
  },
  stars: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  starButton: {
    padding: spacing.xs,
  },
  ratingHint: {
    color: colors.mutedText,
    fontSize: 13,
    textAlign: "center",
  },
  input: {
    minHeight: 110,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    color: colors.text,
    fontSize: 15,
    padding: spacing.sm,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
});
