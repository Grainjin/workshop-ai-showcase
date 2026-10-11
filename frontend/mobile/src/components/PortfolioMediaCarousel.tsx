import { ChevronLeft, ChevronRight, Play } from "lucide-react-native";
import { createElement, useEffect, useRef, useState } from "react";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import {
  Image,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";

import { colors, spacing } from "../theme/theme";
import type { ProviderPortfolio, ProviderPortfolioMedia } from "../types/provider";
import { resolveMediaUrl } from "../utils/media";

type PortfolioMediaCarouselProps = {
  portfolio: ProviderPortfolio;
};

export function PortfolioMediaCarousel({ portfolio }: PortfolioMediaCarouselProps) {
  const { width } = useWindowDimensions();
  const scrollViewRef = useRef<ScrollView | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [activeVideoUrl, setActiveVideoUrl] = useState<string | null>(null);
  const mediaWidth = Math.max(260, Math.min(width - spacing.lg * 2, 780));
  const mediaItems = getPortfolioMediaItems(portfolio);

  useEffect(() => {
    setActiveIndex(0);
  }, [portfolio.id]);

  function handleScrollEnd(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const nextIndex = Math.round(event.nativeEvent.contentOffset.x / mediaWidth);
    setActiveIndex(nextIndex);
  }

  function moveToMedia(nextIndex: number) {
    const safeIndex = Math.max(0, Math.min(nextIndex, mediaItems.length - 1));

    setActiveIndex(safeIndex);
    scrollViewRef.current?.scrollTo({
      x: safeIndex * mediaWidth,
      animated: true,
    });
  }

  async function openMedia(media: ProviderPortfolioMedia) {
    const mediaUrl = resolveMediaUrl(media.file_url);

    if (!mediaUrl) {
      return;
    }

    if (Platform.OS === "web") {
      setActiveVideoUrl(mediaUrl);
      return;
    }

    await Linking.openURL(mediaUrl);
  }

  if (mediaItems.length === 0) {
    return (
      <View style={[styles.emptyBox, { width: mediaWidth }]}>
        <Text style={styles.emptyText}>No portfolio media</Text>
      </View>
    );
  }

  return (
    <View style={{ width: mediaWidth }}>
      <View style={styles.carouselFrame}>
        <ScrollView
          horizontal
          onMomentumScrollEnd={handleScrollEnd}
          pagingEnabled
          ref={scrollViewRef}
          showsHorizontalScrollIndicator={false}
          style={styles.scroller}
        >
          {mediaItems.map((media) => {
            const mediaUrl = resolveMediaUrl(media.file_url);
            const isVideo = media.media_type === "video";

            return (
              <View key={`${media.id}-${media.file_url}`} style={{ width: mediaWidth }}>
                {mediaUrl && !isVideo ? (
                  <Image source={{ uri: mediaUrl }} style={styles.media} />
                ) : (
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => void openMedia(media)}
                    style={styles.videoBox}
                  >
                    <View style={styles.playCircle}>
                      <Play color="#FFFFFF" fill="#FFFFFF" size={34} />
                    </View>
                    <Text style={styles.videoHint}>Tap to play video</Text>
                  </Pressable>
                )}
              </View>
            );
          })}
        </ScrollView>

        {mediaItems.length > 1 ? (
          <>
            <Pressable
              accessibilityLabel="Previous"
              accessibilityRole="button"
              disabled={activeIndex === 0}
              onPress={() => moveToMedia(activeIndex - 1)}
              style={({ pressed }) => [
                styles.arrowButton,
                styles.leftArrow,
                activeIndex === 0 ? styles.arrowDisabled : null,
                pressed ? styles.arrowPressed : null,
              ]}
            >
              <ChevronLeft color="#FFFFFF" size={24} />
            </Pressable>
            <Pressable
              accessibilityLabel="Next"
              accessibilityRole="button"
              disabled={activeIndex === mediaItems.length - 1}
              onPress={() => moveToMedia(activeIndex + 1)}
              style={({ pressed }) => [
                styles.arrowButton,
                styles.rightArrow,
                activeIndex === mediaItems.length - 1 ? styles.arrowDisabled : null,
                pressed ? styles.arrowPressed : null,
              ]}
            >
              <ChevronRight color="#FFFFFF" size={24} />
            </Pressable>
          </>
        ) : null}
      </View>

      {mediaItems.length > 1 ? (
        <View style={styles.dots}>
          {mediaItems.map((media, index) => (
            <View
              key={`${media.id}-${index}`}
              style={[styles.dot, index === activeIndex ? styles.activeDot : null]}
            />
          ))}
        </View>
      ) : null}

      <Modal
        animationType="fade"
        onRequestClose={() => setActiveVideoUrl(null)}
        transparent
        visible={Boolean(activeVideoUrl)}
      >
        <View style={styles.videoModalOverlay}>
          <Pressable
            accessibilityLabel="Close video"
            accessibilityRole="button"
            onPress={() => setActiveVideoUrl(null)}
            style={styles.videoCloseButton}
          >
            <Text style={styles.videoCloseText}>×</Text>
          </Pressable>
          <View style={styles.videoPlayerBox}>
            {activeVideoUrl
              ? createElement("video", {
                  autoPlay: true,
                  controls: true,
                  src: activeVideoUrl,
                  style: {
                    width: "100%",
                    maxHeight: "82vh",
                    borderRadius: 12,
                    backgroundColor: "#000000",
                  },
                })
              : null}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function getPortfolioMediaItems(
  portfolio: ProviderPortfolio,
): ProviderPortfolioMedia[] {
  if (portfolio.media_items?.length) {
    return portfolio.media_items;
  }

  if (!portfolio.image_url) {
    return [];
  }

  return [
    {
      id: 0,
      portfolio_id: portfolio.id,
      file_url: portfolio.image_url,
      original_file_name: portfolio.original_file_name,
      content_type: portfolio.content_type,
      media_type: portfolio.media_type,
      sort_order: 0,
      created_at: portfolio.created_at,
    },
  ];
}

const styles = StyleSheet.create({
  carouselFrame: {
    overflow: "hidden",
    borderRadius: 18,
  },
  scroller: {
    borderRadius: 18,
  },
  media: {
    width: "100%",
    aspectRatio: 1.2,
    backgroundColor: colors.background,
  },
  videoBox: {
    width: "100%",
    aspectRatio: 1.2,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    backgroundColor: colors.text,
  },
  playCircle: {
    width: 74,
    height: 74,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 37,
    backgroundColor: colors.primary,
  },
  videoHint: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
  arrowButton: {
    position: "absolute",
    top: "50%",
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 21,
    backgroundColor: "rgba(0, 0, 0, 0.42)",
    transform: [{ translateY: -21 }],
  },
  leftArrow: {
    left: spacing.sm,
  },
  rightArrow: {
    right: spacing.sm,
  },
  arrowPressed: {
    backgroundColor: "rgba(0, 0, 0, 0.62)",
  },
  arrowDisabled: {
    opacity: 0.28,
  },
  emptyBox: {
    aspectRatio: 1.2,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
    backgroundColor: colors.background,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  dots: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xs,
    paddingTop: spacing.sm,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.border,
  },
  activeDot: {
    width: 18,
    backgroundColor: colors.primary,
  },
  videoModalOverlay: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0, 0, 0, 0.86)",
    padding: spacing.lg,
  },
  videoPlayerBox: {
    width: "100%",
    maxWidth: 900,
  },
  videoCloseButton: {
    position: "absolute",
    top: spacing.lg,
    right: spacing.lg,
    zIndex: 10,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 22,
    backgroundColor: "rgba(255, 255, 255, 0.18)",
  },
  videoCloseText: {
    color: "#FFFFFF",
    fontSize: 34,
    lineHeight: 38,
  },
});
