import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { Play } from "lucide-react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { ProviderPortfolio } from "../types/provider";
import { resolveMediaUrl } from "../utils/media";

type PortfolioCardProps = {
  portfolio: ProviderPortfolio;
  onPress: () => void;
  compact?: boolean;
};

export function PortfolioCard({
  portfolio,
  onPress,
  compact = false,
}: PortfolioCardProps) {
  const coverMedia = portfolio.media_items?.[0];
  const mediaUrl = resolveMediaUrl(coverMedia?.file_url ?? portfolio.image_url);
  const isVideo = (coverMedia?.media_type ?? portfolio.media_type) === "video";

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        compact ? styles.compactCard : null,
        pressed ? styles.cardPressed : null,
      ]}
    >
      <View style={styles.mediaBox}>
        {mediaUrl && !isVideo ? (
          <Image source={{ uri: mediaUrl }} style={styles.image} />
        ) : isVideo ? (
          <View style={styles.videoPlaceholder}>
            <Play color="#FFFFFF" fill="#FFFFFF" size={compact ? 24 : 30} />
          </View>
        ) : (
          <View style={styles.emptyPlaceholder}>
            <Text style={styles.emptyText}>No image</Text>
          </View>
        )}

        {isVideo ? (
          <View style={styles.playBadge}>
            <Play color="#FFFFFF" fill="#FFFFFF" size={14} />
          </View>
        ) : null}
      </View>

      {portfolio.verification_status !== "approved" ? (
        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>{portfolio.verification_status}</Text>
        </View>
      ) : null}

      <Text numberOfLines={2} style={styles.title}>
        {portfolio.title}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "48%",
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
  },
  compactCard: {
    width: 150,
  },
  cardPressed: {
    opacity: 0.76,
  },
  mediaBox: {
    aspectRatio: 1.2,
    backgroundColor: colors.surface,
  },
  image: {
    width: "100%",
    height: "100%",
  },
  videoPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#202123",
  },
  emptyPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
  },
  playBadge: {
    position: "absolute",
    right: spacing.sm,
    bottom: spacing.sm,
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: "rgba(0, 0, 0, 0.58)",
  },
  statusBadge: {
    alignSelf: "flex-start",
    marginTop: spacing.sm,
    marginHorizontal: spacing.sm,
    borderRadius: 999,
    backgroundColor: "#FFF7E6",
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  statusText: {
    color: "#9A5B00",
    fontSize: 11,
    fontWeight: "800",
    textTransform: "capitalize",
  },
  title: {
    minHeight: 44,
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
    padding: spacing.sm,
  },
});
