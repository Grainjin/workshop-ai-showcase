import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { ChevronDown, MapPin, Search } from "lucide-react-native";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  getCustomerHomeRecommendations,
  getCustomerProfile,
  getCustomerProviderDetail,
  updateCustomerServiceProvince,
} from "../../api/customer";
import { PlaceholderPanel } from "../../components/PlaceholderPanel";
import { LocationCascadePickerModal } from "../../components/LocationCascadePickerModal";
import { ProviderRecommendationCard } from "../../components/ProviderRecommendationCard";
import { useRealtime } from "../../context/RealtimeContext";
import { ScreenContainer } from "../../components/ScreenContainer";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors, radius, spacing } from "../../theme/theme";
import type { ProviderRecommendation } from "../../types/provider";
import type { ServiceAreaSelection } from "../../types/location";
import { createLatestRequestGuard } from "../../utils/latestRequest";
import {
  DEFAULT_PROVIDER_TAG,
  getProviderTagLabel,
  PROVIDER_TAGS,
} from "../../constants/providerTags";

export function CustomerHomeScreen() {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { subscribe } = useRealtime();
  const [keyword, setKeyword] = useState("");
  const [selectedTag, setSelectedTag] = useState("");
  const [selectedProvince, setSelectedProvince] = useState("Istanbul");
  const [selectedLocationId, setSelectedLocationId] = useState<number | null>(null);
  const [selectedAreaLabel, setSelectedAreaLabel] = useState("Istanbul");
  const [isProvinceModalVisible, setIsProvinceModalVisible] = useState(false);
  const [provinceMessage, setProvinceMessage] = useState("");
  const [isSavingProvince, setIsSavingProvince] = useState(false);
  const [historyProviderTag, setHistoryProviderTag] = useState<string>(
    DEFAULT_PROVIDER_TAG,
  );
  const [recommendations, setRecommendations] = useState<
    ProviderRecommendation[]
  >([]);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [recommendationWidth, setRecommendationWidth] = useState(0);
  const recommendationRequestGuard = useRef(createLatestRequestGuard()).current;
  const recommendationLayout = getRecommendationLayout(recommendationWidth);

  useEffect(() => {
    let isMounted = true;

    getCustomerProfile()
      .then((profile) => {
        if (isMounted && profile?.service_province) {
          setSelectedProvince(profile.service_province);
          setSelectedLocationId(profile.service_location_id);
          setSelectedAreaLabel(profile.service_province);
        }
      })
      .catch(() => undefined);

    return () => {
      isMounted = false;
    };
  }, []);

  const loadRecommendations = useCallback(async () => {
    const generation = recommendationRequestGuard.begin();
    setIsLoadingRecommendations(true);

    try {
      const data = await getCustomerHomeRecommendations(
        selectedProvince,
        selectedTag,
        selectedLocationId ?? undefined,
      );
      if (!recommendationRequestGuard.isLatest(generation)) return;
      setHistoryProviderTag(data?.history_provider_tag ?? DEFAULT_PROVIDER_TAG);
      setRecommendations(data?.items ?? []);
    } catch {
      if (recommendationRequestGuard.isLatest(generation)) setRecommendations([]);
    } finally {
      if (recommendationRequestGuard.isLatest(generation)) setIsLoadingRecommendations(false);
    }
  }, [recommendationRequestGuard, selectedLocationId, selectedProvince, selectedTag]);

  useFocusEffect(
    useCallback(() => {
      void loadRecommendations();
      return () => recommendationRequestGuard.invalidate();
    }, [loadRecommendations, recommendationRequestGuard]),
  );

  useEffect(() => {
    const unsubscribe = subscribe((data) => {
      if (
        (data.type === "user_online" || data.type === "user_offline") &&
        typeof data.user_id === "number"
      ) {
        const userId = data.user_id;

        setRecommendations((currentRecommendations) =>
          updateProviderOnline(
            currentRecommendations,
            userId,
            data.type === "user_online",
          ),
        );
      }
    });

    return unsubscribe;
  }, [subscribe]);

  async function handleSelectServiceArea(selection: ServiceAreaSelection) {
    setSelectedProvince(selection.serviceProvince);
    setSelectedLocationId(selection.serviceLocationId);
    setSelectedAreaLabel(selection.label);
    setIsProvinceModalVisible(false);
    setProvinceMessage("Saving area...");
    setIsSavingProvince(true);

    try {
      await updateCustomerServiceProvince(
        selection.serviceProvince,
        selection.serviceLocationId,
      );
      setProvinceMessage("Service area saved.");
    } catch {
      setProvinceMessage("Couldn't save service area. Try again.");
    } finally {
      setIsSavingProvince(false);
    }
  }

  function handleSearchSubmit() {
    const searchText = keyword.trim() || selectedTag;

    if (!searchText) {
      setProvinceMessage("Enter a search term or choose a service.");
      return;
    }

    setProvinceMessage(`Searching in ${selectedProvince}: ${searchText}`);
    navigation.navigate("CustomerProviderSearchResults", {
      keyword: searchText,
      serviceProvince: selectedProvince,
      serviceLocationId: selectedLocationId ?? undefined,
      serviceAreaLabel: selectedAreaLabel,
      category: selectedTag || undefined,
    });
  }

  async function handleOpenProvider(provider: ProviderRecommendation) {
    try {
      const detail = await getCustomerProviderDetail(provider.id);
      navigation.navigate("CustomerProviderDetail", {
        providerId: provider.id,
        providerTag: detail?.history.last_provider_tag ?? provider.tags[0],
      });
    } catch {
      setProvinceMessage("Couldn't open this profile.");
    }
  }

  return (
    <ScreenContainer>
      <View style={styles.searchRow}>
        <Pressable
          accessibilityLabel="Service area"
          accessibilityRole="button"
          onPress={() => setIsProvinceModalVisible(true)}
          style={styles.provinceButton}
        >
          <MapPin color={colors.primary} size={20} />
          <Text style={styles.provinceButtonText} numberOfLines={1}>
            {selectedAreaLabel}
          </Text>
          <ChevronDown color={colors.mutedText} size={17} />
        </Pressable>

        <View style={styles.searchBox}>
          <Search color={colors.mutedText} size={20} />
          <TextInput
            onChangeText={setKeyword}
            onSubmitEditing={handleSearchSubmit}
            placeholder="Search services or businesses"
            placeholderTextColor={colors.mutedText}
            returnKeyType="search"
            style={styles.searchInput}
            value={keyword}
          />
        </View>
      </View>

      <Text style={styles.provinceStatusText} numberOfLines={2}>
        {isSavingProvince
          ? "Saving area..."
          : provinceMessage || selectedAreaLabel}
      </Text>

      <View style={styles.header}>
        <Text style={styles.title}>Home</Text>
        <Text style={styles.subtitle}>
          Search listings, read reviews, and book services.
        </Text>
      </View>

      <View style={styles.tagSection}>
        <Text style={styles.sectionTitle}>Popular services</Text>
        <View style={styles.tagGrid}>
          {PROVIDER_TAGS.map((tag) => {
            const isActive = selectedTag === tag;

            return (
              <Pressable
                accessibilityRole="button"
                key={tag}
                onPress={() => {
                  setSelectedTag(isActive ? "" : tag);
                  setProvinceMessage("");
                }}
                style={[styles.tagChip, isActive ? styles.tagChipActive : null]}
              >
                <Text
                  style={[styles.tagText, isActive ? styles.tagTextActive : null]}
                >
                  {getProviderTagLabel(tag)}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <View
        onLayout={(event) =>
          setRecommendationWidth(event.nativeEvent.layout.width)
        }
        style={styles.recommendationSection}
      >
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>
            {selectedTag ? `${getProviderTagLabel(selectedTag)}` : "Recommended"}
          </Text>
          <Text style={styles.historyText}>
            {selectedTag
              ? selectedAreaLabel
              : `Based on ${getProviderTagLabel(historyProviderTag).toLowerCase()}`}
          </Text>
        </View>

        {isLoadingRecommendations ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.loadingText}>Loading recommendations...</Text>
          </View>
        ) : recommendations.length > 0 ? (
          <View style={styles.recommendationGrid}>
            {recommendations.map((provider) => (
              <ProviderRecommendationCard
                cardWidth={recommendationLayout.cardWidth}
                key={provider.id}
                onPress={(selectedProvider) => void handleOpenProvider(selectedProvider)}
                provider={provider}
              />
            ))}
          </View>
        ) : (
          <PlaceholderPanel
            title={selectedTag ? "No providers found" : "No recommendations yet"}
            description={
              selectedTag
                ? `No ${getProviderTagLabel(selectedTag).toLowerCase()} providers in ${selectedAreaLabel}.`
                : `No recommendations in ${selectedAreaLabel} yet.`
            }
          />
        )}
      </View>

      <LocationCascadePickerModal
        onClose={() => setIsProvinceModalVisible(false)}
        onSelect={(selection) => void handleSelectServiceArea(selection)}
        value={
          selectedLocationId
            ? {
                serviceLocationId: selectedLocationId,
                serviceProvince: selectedProvince,
                label: selectedAreaLabel,
              }
            : null
        }
        visible={isProvinceModalVisible}
      />
    </ScreenContainer>
  );
}

function updateProviderOnline(
  providers: ProviderRecommendation[],
  userId: number,
  isOnline: boolean,
) {
  return providers.map((provider) =>
    provider.user_id === userId ? { ...provider, is_online: isOnline } : provider,
  );
}

const styles = StyleSheet.create({
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
  },
  subtitle: {
    color: colors.mutedText,
    fontSize: 16,
    lineHeight: 23,
  },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  provinceButton: {
    maxWidth: 132,
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.sm,
  },
  provinceButtonText: {
    flexShrink: 1,
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  searchBox: {
    flex: 1,
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    color: colors.text,
    fontSize: 16,
  },
  provinceStatusText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  header: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  tagSection: {
    gap: spacing.sm,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
  },
  sectionHeaderRow: {
    minHeight: 26,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  historyText: {
    flexShrink: 1,
    color: colors.mutedText,
    fontSize: 13,
  },
  tagGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  tagChip: {
    minHeight: 38,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
  },
  tagChipActive: {
    borderColor: colors.primary,
    backgroundColor: "#E9F7F3",
  },
  tagText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  tagTextActive: {
    color: colors.primary,
  },
  recommendationSection: {
    gap: spacing.sm,
  },
  loadingBox: {
    minHeight: 120,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
  },
  loadingText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  recommendationGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "flex-start",
    maxWidth: "100%",
    gap: spacing.md,
  },
});

function getRecommendationLayout(windowWidth: number) {
  const columns = windowWidth >= 1100 ? 5 : windowWidth >= 720 ? 4 : 2;
  const gridGapTotal = spacing.md * (columns - 1);
  const fallbackCardWidth = columns === 4 ? 180 : 150;
  const cardWidth =
    windowWidth > 0
      ? Math.floor((windowWidth - gridGapTotal) / columns)
      : fallbackCardWidth;

  return {
    cardWidth,
  };
}
