import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { Heart, MessageCircle, Send } from "lucide-react-native";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  addCustomerFavourite,
  createCustomerBooking,
  getCustomerProviderDetail,
  getPublicProviderPortfolios,
  getPublicProviderReviews,
  openChatWithProvider,
  removeCustomerFavourite,
} from "../../api/customer";
import {
  BookingRequestModal,
  buildBookingRequestPayload,
  createDefaultBookingRequestForm,
  type BookingRequestFormState,
} from "../../components/BookingRequestModal";
import { PortfolioCard } from "../../components/PortfolioCard";
import { useRealtime } from "../../context/RealtimeContext";
import { setProviderFavouriteState } from "../../features/favourites/favourite-state";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors, spacing } from "../../theme/theme";
import type { PaginatedData } from "../../types/chat";
import type {
  CustomerProviderDetail,
  ProviderPortfolio,
  ProviderProfile,
  ProviderServiceArea,
} from "../../types/provider";
import type { Review } from "../../types/review";
import { getErrorMessage } from "../../utils/errors";

type CustomerProviderDetailScreenProps = NativeStackScreenProps<
  RootStackParamList,
  "CustomerProviderDetail"
>;

const REVIEW_PAGE_SIZE = 10;

export function CustomerProviderDetailScreen({
  navigation,
  route,
}: CustomerProviderDetailScreenProps) {
  const { subscribe } = useRealtime();
  const [detail, setDetail] = useState<CustomerProviderDetail | null>(null);
  const [portfolios, setPortfolios] = useState<ProviderPortfolio[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewPage, setReviewPage] = useState(1);
  const [reviewPaging, setReviewPaging] = useState<PaginatedData<Review> | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isOpeningChat, setIsOpeningChat] = useState(false);
  const [isUpdatingFavourite, setIsUpdatingFavourite] = useState(false);
  const [favouriteMessage, setFavouriteMessage] = useState("");
  const [isBookingModalVisible, setIsBookingModalVisible] = useState(false);
  const [isSubmittingBooking, setIsSubmittingBooking] = useState(false);
  const [bookingError, setBookingError] = useState("");
  const [message, setMessage] = useState("");
  const [bookingForm, setBookingForm] = useState<BookingRequestFormState>(
    createDefaultBookingRequestForm(),
  );

  useEffect(() => {
    let isActive = true;

    async function loadProvider() {
      setIsLoading(true);
      setMessage("");
      setFavouriteMessage("");

      try {
        const [nextDetail, portfolioPage, reviewPageData] = await Promise.all([
          getCustomerProviderDetail(route.params.providerId),
          getPublicProviderPortfolios(route.params.providerId, 1, 4),
          getPublicProviderReviews(route.params.providerId, 1, REVIEW_PAGE_SIZE),
        ]);

        if (isActive) {
          setDetail(nextDetail);
          setPortfolios(portfolioPage?.items ?? []);
          setReviews(reviewPageData?.items ?? []);
          setReviewPaging(reviewPageData);
          setReviewPage(1);
        }
      } catch {
        if (isActive) {
          setMessage("Couldn't load this profile.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadProvider();

    return () => {
      isActive = false;
    };
  }, [route.params.providerId]);

  useEffect(() => {
    const unsubscribe = subscribe((data) => {
      if (
        (data.type === "user_online" || data.type === "user_offline") &&
        typeof data.user_id === "number"
      ) {
        setDetail((currentDetail) => {
          if (!currentDetail || currentDetail.provider.user_id !== data.user_id) {
            return currentDetail;
          }

          return {
            ...currentDetail,
            provider: {
              ...currentDetail.provider,
              is_online: data.type === "user_online",
            },
          };
        });
      }
    });

    return unsubscribe;
  }, [subscribe]);

  async function loadMoreReviews() {
    if (isLoadingMore || !reviewPaging?.has_next) {
      return;
    }

    setIsLoadingMore(true);
    try {
      const nextPage = reviewPage + 1;
      const nextData = await getPublicProviderReviews(
        route.params.providerId,
        nextPage,
        REVIEW_PAGE_SIZE,
      );

      if (nextData) {
        setReviews((current) => [...current, ...nextData.items]);
        setReviewPaging(nextData);
        setReviewPage(nextPage);
      }
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleOpenChat() {
    const provider = detail?.provider;

    if (!provider || isOpeningChat) {
      return;
    }

    setIsOpeningChat(true);
    try {
      const result = await openChatWithProvider(provider.id);

      if (result?.chat_room) {
        navigation.navigate("ChatRoom", {
          chatRoomId: result.chat_room.id,
          title: provider.business_name,
          opponentOnline: provider.is_online,
          providerProfileId: provider.id,
        });
      }
    } catch {
      Alert.alert("Couldn't start chat", "Try again.");
    } finally {
      setIsOpeningChat(false);
    }
  }

  async function handleToggleFavourite() {
    const provider = detail?.provider;

    if (!detail || !provider || isUpdatingFavourite) {
      return;
    }

    setIsUpdatingFavourite(true);
    setFavouriteMessage("");
    try {
      if (provider.is_favorited) {
        await removeCustomerFavourite(provider.id);
      } else {
        await addCustomerFavourite(provider.id);
      }

      setDetail((currentDetail) =>
        currentDetail
          ? setProviderFavouriteState(
              currentDetail,
              !currentDetail.provider.is_favorited,
            )
          : currentDetail,
      );
    } catch (error) {
      setFavouriteMessage(getErrorMessage(error));
    } finally {
      setIsUpdatingFavourite(false);
    }
  }

  function openBookingModal() {
    setBookingForm(createDefaultBookingRequestForm(detail?.provider));
    setBookingError("");
    setIsBookingModalVisible(true);
  }

  async function handleCreateBooking() {
    const provider = detail?.provider;
    const payload = provider
      ? buildBookingRequestPayload({
          provider,
          providerProfileId: provider.id,
          form: bookingForm,
        })
      : null;

    if (!provider || !payload) {
      setBookingError("Select a service and enter a title (maximum 30 words), description, address, and schedule.");
      return;
    }

    setIsSubmittingBooking(true);
    setBookingError("");
    try {
      const result = await createCustomerBooking(payload);

      if (result?.chat_room) {
        setIsBookingModalVisible(false);
        navigation.navigate("ChatRoom", {
          chatRoomId: result.chat_room.id,
          title: provider.business_name,
          opponentOnline: provider.is_online,
          providerProfileId: provider.id,
        });
      }
    } catch (error) {
      setBookingError(getErrorMessage(error));
    } finally {
      setIsSubmittingBooking(false);
    }
  }

  const provider = detail?.provider;

  return (
    <>
      <FlatList
        ListEmptyComponent={
          isLoading ? null : (
            <Text style={styles.emptyText}>{message || "No reviews yet"}</Text>
          )
        }
        ListFooterComponent={
          isLoadingMore ? (
            <ActivityIndicator color={colors.primary} style={styles.footerLoader} />
          ) : null
        }
        ListHeaderComponent={
          <View style={styles.headerContent}>
            {isLoading ? (
              <View style={styles.centerBox}>
                <ActivityIndicator color={colors.primary} />
                <Text style={styles.emptyText}>Loading provider profile...</Text>
              </View>
            ) : provider ? (
              <>
                <View style={styles.profileCard}>
                  <View style={styles.profileTextBox}>
                    <View style={styles.businessTitleRow}>
                      <Text numberOfLines={1} style={styles.businessName}>
                        {provider.business_name}
                      </Text>
                    </View>
                    <View style={styles.statusRow}>
                      <OpenStatusBadge isOpen={provider.is_open} />
                      <OnlineStatusBadge isOnline={provider.is_online} />
                    </View>
                    {favouriteMessage ? (
                      <Text style={styles.favouriteErrorText}>
                        {favouriteMessage}
                      </Text>
                    ) : null}
                    <Text style={styles.bioText}>{provider.bio}</Text>
                    <Text style={styles.metaText}>
                      Business address: {provider.address || "Not set"}
                    </Text>
                    <Text style={styles.metaText}>
                      Service areas: {formatServiceAreas(provider.service_areas)}
                    </Text>
                    <Text style={styles.metaText}>
                      {formatRating(provider)} · {provider.hourly_rate} / hr
                    </Text>
                    <View style={styles.tagWrap}>
                      {provider.tags.map((tag) => (
                        <View key={tag} style={styles.tagPill}>
                          <Text style={styles.tagText}>{tag}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                  <View style={styles.actionColumn}>
                    <Pressable
                      accessibilityLabel={
                        provider.is_favorited
                          ? "Remove provider from favourites"
                          : "Add provider to favourites"
                      }
                      accessibilityRole="button"
                      accessibilityState={{
                        busy: isUpdatingFavourite,
                        selected: provider.is_favorited,
                      }}
                      disabled={isUpdatingFavourite}
                      onPress={() => void handleToggleFavourite()}
                      style={({ pressed }) => [
                        styles.iconActionButton,
                        styles.favouriteActionButton,
                        pressed && !isUpdatingFavourite
                          ? styles.favouriteActionButtonPressed
                          : null,
                        isUpdatingFavourite ? styles.actionButtonDisabled : null,
                      ]}
                    >
                      <Heart
                        color={colors.primary}
                        fill={provider.is_favorited ? colors.primary : "transparent"}
                        size={20}
                      />
                      <Text style={styles.favouriteActionText}>
                        {provider.is_favorited ? "Saved" : "Save"}
                      </Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      disabled={isOpeningChat}
                      onPress={() => void handleOpenChat()}
                      style={styles.iconActionButton}
                    >
                      <MessageCircle color="#FFFFFF" size={20} />
                      <Text style={styles.iconActionText}>Chat</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      onPress={openBookingModal}
                      style={styles.iconActionButton}
                    >
                      <Send color="#FFFFFF" size={20} />
                      <Text style={styles.iconActionText}>Book</Text>
                    </Pressable>
                  </View>
                </View>

                <Text style={styles.sectionTitle}>Portfolios</Text>
                {portfolios.length > 0 ? (
                  <FlatList
                    ItemSeparatorComponent={() => <View style={styles.portfolioGap} />}
                    data={portfolios}
                    horizontal
                    keyExtractor={(item) => String(item.id)}
                    renderItem={({ item }) => (
                      <PortfolioCard
                        compact
                        onPress={() =>
                          navigation.navigate("CustomerProviderPortfolioDetail", {
                            providerId: provider.id,
                            portfolioId: item.id,
                          })
                        }
                        portfolio={item}
                      />
                    )}
                    showsHorizontalScrollIndicator={false}
                  />
                ) : (
                  <Text style={styles.emptyText}>No portfolios to preview</Text>
                )}

                <Text style={styles.sectionTitle}>Reviews</Text>
              </>
            ) : (
              <Text style={styles.emptyText}>{message || "Provider not found"}</Text>
            )}
          </View>
        }
        contentContainerStyle={styles.content}
        data={reviews}
        keyExtractor={(item) => String(item.id)}
        onEndReached={() => void loadMoreReviews()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => <ReviewRow review={item} />}
        style={styles.container}
      />

      <BookingRequestModal
        bookingForm={bookingForm}
        errorMessage={bookingError}
        isLoading={isSubmittingBooking}
        onClose={() => setIsBookingModalVisible(false)}
        onSubmit={() => void handleCreateBooking()}
        serviceCategories={detail?.provider.tags ?? []}
        setBookingForm={setBookingForm}
        visible={isBookingModalVisible}
      />
    </>
  );
}

function formatRating(provider: ProviderProfile) {
  if (provider.average_rating == null || !provider.review_count) {
    return "No rating yet";
  }

  return `${provider.average_rating.toFixed(1)} stars · ${provider.review_count} reviews`;
}

function formatServiceAreas(areas: ProviderServiceArea[] | undefined) {
  return areas?.length
    ? areas.map((area) => area.label || area.name).join(", ")
    : "Not set";
}

function ReviewRow({ review }: { review: Review }) {
  return (
    <View style={styles.reviewCard}>
      <View style={styles.reviewTopRow}>
        <Text style={styles.ratingText}>{review.rating.toFixed(1)} stars</Text>
        <Text style={styles.reviewDate}>{formatDate(review.created_at)}</Text>
      </View>
      <Text style={styles.reviewComment}>
        {review.comment || "No written review"}
      </Text>
    </View>
  );
}

function OnlineStatusBadge({ isOnline }: { isOnline: boolean }) {
  return (
    <View style={styles.onlineBadge}>
      <View
        style={[
          styles.onlineDot,
          isOnline ? styles.onlineDotActive : styles.onlineDotInactive,
        ]}
      />
      <Text style={styles.onlineText}>{isOnline ? "Online" : "Offline"}</Text>
    </View>
  );
}

function OpenStatusBadge({ isOpen }: { isOpen: boolean }) {
  return (
    <View style={styles.onlineBadge}>
      <View
        style={[
          styles.onlineDot,
          isOpen ? styles.onlineDotActive : styles.onlineDotInactive,
        ]}
      />
      <Text style={styles.onlineText}>{isOpen ? "Open" : "Closed"}</Text>
    </View>
  );
}

function formatDate(value: string | null) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10);
  }

  return date.toLocaleDateString();
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
  },
  headerContent: {
    gap: spacing.lg,
  },
  centerBox: {
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xl,
  },
  profileCard: {
    flexDirection: "row",
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  profileTextBox: {
    flex: 1,
    gap: spacing.sm,
  },
  businessName: {
    flex: 1,
    color: colors.text,
    fontSize: 24,
    fontWeight: "800",
  },
  businessTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  statusRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  onlineBadge: {
    minHeight: 26,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.sm,
  },
  onlineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  onlineDotActive: {
    backgroundColor: colors.primary,
  },
  onlineDotInactive: {
    backgroundColor: "#A0A4AE",
  },
  onlineText: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "800",
  },
  bioText: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  metaText: {
    color: colors.mutedText,
    fontSize: 13,
  },
  tagWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  tagPill: {
    borderRadius: 999,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  tagText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "700",
  },
  actionColumn: {
    width: 72,
    gap: spacing.sm,
  },
  iconActionButton: {
    minHeight: 68,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: 14,
    backgroundColor: colors.primary,
  },
  favouriteActionButton: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.background,
  },
  favouriteActionButtonPressed: {
    backgroundColor: colors.surface,
  },
  actionButtonDisabled: {
    opacity: 0.55,
  },
  iconActionText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
  },
  favouriteActionText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
  },
  favouriteErrorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "800",
  },
  portfolioGap: {
    width: spacing.md,
  },
  reviewCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  reviewTopRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  ratingText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
  },
  reviewDate: {
    color: colors.mutedText,
    fontSize: 13,
  },
  reviewComment: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 21,
  },
  footerLoader: {
    paddingVertical: spacing.lg,
  },
  modalOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0, 0, 0, 0.28)",
  },
  modalCard: {
    maxHeight: "92%",
    gap: spacing.md,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  modalTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "800",
  },
  modalActions: {
    flexDirection: "row",
    gap: spacing.md,
  },
});
