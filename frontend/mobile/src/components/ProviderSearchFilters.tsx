import { ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react-native";
import type { ReactNode } from "react";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { getProviderTagLabel, PROVIDER_TAGS } from "../constants/providerTags";
import {
  countActiveSearchFilters,
  getSearchFilterSummary,
  getSearchFilterValidationError,
  type ProviderSearchFilters as ProviderSearchFilterValues,
  type ProviderSearchSort,
} from "../features/provider-search/search-filter-state";
import { colors, radius, spacing } from "../theme/theme";
import { SecondaryButton } from "./SecondaryButton";

type ProviderSearchFiltersProps = {
  value: ProviderSearchFilterValues;
  onChange: (value: ProviderSearchFilterValues) => void;
  onApply: () => void;
  onClear: () => void;
  isApplying?: boolean;
  distanceEnabled?: boolean;
  distanceDisabledReason?: string;
};

const DISTANCE_OPTIONS = [5, 10, 25, 50] as const;
const RATING_OPTIONS = [3, 4, 4.5] as const;
const SORT_OPTIONS: Array<{ label: string; value: ProviderSearchSort }> = [
  { label: "Recommended", value: "recommended" },
  { label: "Nearest", value: "nearest" },
  { label: "Lowest price", value: "lowestPrice" },
  { label: "Highest rating", value: "highestRating" },
];

export function ProviderSearchFilters({
  value,
  onChange,
  onApply,
  onClear,
  isApplying = false,
  distanceEnabled = true,
  distanceDisabledReason,
}: ProviderSearchFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const activeCount = countActiveSearchFilters(value);
  const summary = getSearchFilterSummary(value);
  const validationError = getSearchFilterValidationError(value);
  const applyDisabled = isApplying || validationError !== null;

  function update<Key extends keyof ProviderSearchFilterValues>(
    key: Key,
    nextValue: ProviderSearchFilterValues[Key],
  ) {
    onChange({ ...value, [key]: nextValue });
  }

  function handleApply() {
    onApply();
    setIsExpanded(false);
  }

  return (
    <View style={styles.panel}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: isExpanded }}
        onPress={() => setIsExpanded((current) => !current)}
        style={({ pressed }) => [
          styles.collapsedBar,
          pressed ? styles.collapsedBarPressed : null,
        ]}
      >
        <SlidersHorizontal color={colors.text} size={20} />
        <View style={styles.collapsedText}>
          <View style={styles.headingRow}>
            <Text style={styles.title}>Filter and sort</Text>
            {activeCount > 0 ? (
              <View style={styles.countBadge}>
                <Text style={styles.countText}>{activeCount}</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.summaryText} numberOfLines={1}>
            {summary}
          </Text>
        </View>
        {isExpanded ? (
          <ChevronUp color={colors.mutedText} size={20} />
        ) : (
          <ChevronDown color={colors.mutedText} size={20} />
        )}
      </Pressable>

      {isExpanded ? (
        <>
          <View style={styles.actionsRow}>
            <Text style={styles.expandedLabel}>Refine results</Text>
            <SecondaryButton
              disabled={activeCount === 0 || isApplying}
              label="Clear"
              onPress={onClear}
            />
          </View>

          <FilterSection label="Category">
            <View style={styles.chipRow}>
              {PROVIDER_TAGS.map((tag) => (
                <FilterChip
                  active={value.category === tag}
                  key={tag}
                  label={getProviderTagLabel(tag)}
                  onPress={() =>
                    update("category", value.category === tag ? null : tag)
                  }
                />
              ))}
            </View>
          </FilterSection>

          <View style={styles.twoColumnRow}>
            <FilterSection label="Maximum distance">
              <View style={styles.chipRow}>
                {DISTANCE_OPTIONS.map((distance) => (
                  <FilterChip
                    active={value.maxDistanceKm === distance}
                    disabled={!distanceEnabled}
                    key={distance}
                    label={`${distance} km`}
                    onPress={() =>
                      update(
                        "maxDistanceKm",
                        value.maxDistanceKm === distance ? null : distance,
                      )
                    }
                  />
                ))}
              </View>
              {!distanceEnabled && distanceDisabledReason ? (
                <Text style={styles.helperText}>{distanceDisabledReason}</Text>
              ) : null}
            </FilterSection>

            <FilterSection label="Minimum rating">
              <View style={styles.chipRow}>
                {RATING_OPTIONS.map((rating) => (
                  <FilterChip
                    active={value.minRating === rating}
                    key={rating}
                    label={`${rating}+ stars`}
                    onPress={() =>
                      update("minRating", value.minRating === rating ? null : rating)
                    }
                  />
                ))}
              </View>
            </FilterSection>
          </View>

          <FilterSection label="Hourly price">
            <View style={styles.priceRow}>
              <TextInput
                accessibilityLabel="Minimum hourly price"
                inputMode="numeric"
                onChangeText={(text) => update("minPrice", text)}
                placeholder="Minimum"
                placeholderTextColor={colors.mutedText}
                style={styles.priceInput}
                value={value.minPrice}
              />
              <Text style={styles.priceSeparator}>to</Text>
              <TextInput
                accessibilityLabel="Maximum hourly price"
                inputMode="numeric"
                onChangeText={(text) => update("maxPrice", text)}
                placeholder="Maximum"
                placeholderTextColor={colors.mutedText}
                style={styles.priceInput}
                value={value.maxPrice}
              />
            </View>
          </FilterSection>

          <FilterSection label="Availability">
            <View style={styles.chipRow}>
              <FilterChip
                active={value.availability === "any"}
                label="Any"
                onPress={() => update("availability", "any")}
              />
              <FilterChip
                active={value.availability === "open"}
                label="Open"
                onPress={() => update("availability", "open")}
              />
              <FilterChip
                active={value.availability === "closed"}
                label="Closed"
                onPress={() => update("availability", "closed")}
              />
            </View>
          </FilterSection>

          <FilterSection label="Sort by">
            <View style={styles.chipRow}>
              {SORT_OPTIONS.map((option) => (
                <FilterChip
                  active={value.sort === option.value}
                  disabled={option.value === "nearest" && !distanceEnabled}
                  key={option.value}
                  label={option.label}
                  onPress={() => update("sort", option.value)}
                />
              ))}
            </View>
          </FilterSection>

          {validationError ? (
            <Text accessibilityRole="alert" style={styles.errorText}>
              {validationError}
            </Text>
          ) : null}

          <Pressable
            accessibilityRole="button"
            disabled={applyDisabled}
            onPress={handleApply}
            style={({ pressed }) => [
              styles.applyButton,
              pressed && !applyDisabled ? styles.applyButtonPressed : null,
              applyDisabled ? styles.disabled : null,
            ]}
          >
            <Text style={styles.applyText}>
              {isApplying ? "Applying..." : "Apply filters"}
            </Text>
          </Pressable>
        </>
      ) : null}
    </View>
  );
}

function FilterSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionLabel}>{label}</Text>
      {children}
    </View>
  );
}

function FilterChip({
  active,
  label,
  onPress,
  disabled = false,
}: {
  active: boolean;
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled, selected: active }}
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.chip,
        active ? styles.chipActive : null,
        disabled ? styles.disabled : null,
      ]}
    >
      <Text style={[styles.chipText, active ? styles.chipTextActive : null]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: {
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  collapsedBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  collapsedBarPressed: { opacity: 0.72 },
  collapsedText: { flex: 1, minWidth: 0, gap: spacing.xs },
  headingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  summaryText: { color: colors.mutedText, fontSize: 13 },
  actionsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  expandedLabel: { color: colors.text, fontSize: 14, fontWeight: "700" },
  title: { color: colors.text, fontSize: 18, fontWeight: "700" },
  countBadge: {
    minWidth: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xs,
  },
  countText: { color: "#FFFFFF", fontSize: 12, fontWeight: "800" },
  section: { flex: 1, minWidth: 0, gap: spacing.sm },
  sectionLabel: { color: colors.text, fontSize: 14, fontWeight: "700" },
  twoColumnRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    minHeight: 38,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  chipActive: { borderColor: colors.primary, backgroundColor: "#E7F6F2" },
  chipText: { color: colors.text, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: colors.primary },
  priceRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  priceInput: {
    minWidth: 120,
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    color: colors.text,
    paddingHorizontal: spacing.md,
  },
  priceSeparator: { color: colors.mutedText, fontSize: 13 },
  applyButton: {
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
  },
  applyButtonPressed: { backgroundColor: colors.primaryPressed },
  applyText: { color: "#FFFFFF", fontSize: 15, fontWeight: "700" },
  errorText: { color: colors.danger, fontSize: 13, lineHeight: 18 },
  helperText: { color: colors.mutedText, fontSize: 12, lineHeight: 17 },
  disabled: { opacity: 0.55 },
});
