import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import { getProviderTagLabel } from "../constants/providerTags";
import {
  formatProviderDistance,
  getProviderCardImageUrl,
  getProviderCardStatus,
} from "../features/provider-search/provider-card-display";
import { colors, radius, spacing } from "../theme/theme";
import type { ProviderRecommendation } from "../types/provider";
import { resolveMediaUrl } from "../utils/media";

type ProviderRecommendationCardProps = {
  provider: ProviderRecommendation;
  onPress: (provider: ProviderRecommendation) => void;
  cardWidth?: number;
  variant?: "recommendation" | "searchResult";
};

export function ProviderRecommendationCard({
  provider,
  onPress,
  cardWidth,
  variant = "recommendation",
}: ProviderRecommendationCardProps) {
  const isSearchResult = variant === "searchResult";
  const imageUrl = resolveMediaUrl(
    isSearchResult
      ? getProviderCardImageUrl({
          avatarUrl: provider.avatar_url,
          portfolioImageUrl: provider.first_portfolio_image_url,
        })
      : provider.first_portfolio_image_url,
  );
  const status = isSearchResult
    ? getProviderCardStatus({
        isOpen: provider.is_open,
        isOnline: provider.is_online,
      })
    : {
        label: provider.is_online ? "Online" : "Offline",
        tone: provider.is_online ? "active" : "inactive",
      };
  const distance = formatProviderDistance(provider.distance_km);
  const category = getProviderTagLabel(provider.tags[0] ?? "other");

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => onPress(provider)}
      style={[styles.card, cardWidth ? { width: cardWidth } : null]}
    >
      {imageUrl ? (
        <Image source={{ uri: imageUrl }} style={styles.image} />
      ) : (
        <View style={styles.imagePlaceholder}>
          <Text style={styles.imagePlaceholderText}>No image</Text>
        </View>
      )}

      <View style={styles.body}>
        <View style={styles.statusRow}>
          <View
            style={[
              styles.statusDot,
              status.tone === "active"
                ? styles.statusDotActive
                : styles.statusDotInactive,
            ]}
          />
          <Text style={styles.statusText}>{status.label}</Text>
        </View>
        <Text style={styles.name} numberOfLines={2}>
          {provider.business_name}
        </Text>
        <Text style={styles.category} numberOfLines={1}>
          {isSearchResult ? category : provider.tags.join(" · ")}
        </Text>
        {isSearchResult && distance ? (
          <Text style={styles.distance}>{distance}</Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 160,
    flexGrow: 0,
    flexShrink: 0,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
  },
  image: {
    width: "100%",
    aspectRatio: 1.08,
    backgroundColor: colors.surface,
  },
  imagePlaceholder: {
    width: "100%",
    aspectRatio: 1.08,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  imagePlaceholderText: {
    color: colors.mutedText,
    fontSize: 13,
  },
  body: {
    gap: spacing.xs,
    padding: spacing.sm,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusDotActive: {
    backgroundColor: colors.primary,
  },
  statusDotInactive: {
    backgroundColor: "#A0A4AE",
  },
  statusText: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "700",
  },
  name: {
    minHeight: 40,
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 20,
  },
  category: {
    color: colors.mutedText,
    fontSize: 12,
    lineHeight: 17,
  },
  distance: {
    color: colors.mutedText,
    fontSize: 12,
    lineHeight: 17,
  },
});
