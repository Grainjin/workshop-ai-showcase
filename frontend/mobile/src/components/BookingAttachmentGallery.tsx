import { FileText, Play } from "lucide-react-native";
import { Image, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { BookingAttachment } from "../types/booking";
import { resolveMediaUrl } from "../utils/media";

type BookingAttachmentGalleryProps = {
  attachments: BookingAttachment[];
  title: string;
};

export function BookingAttachmentGallery({
  attachments,
  title,
}: BookingAttachmentGalleryProps) {
  if (attachments.length === 0) {
    return null;
  }

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.grid}>
        {attachments.map((attachment) => (
          <AttachmentItem attachment={attachment} key={attachment.id} title={title} />
        ))}
      </View>
    </View>
  );
}

function AttachmentItem({
  attachment,
  title,
}: {
  attachment: BookingAttachment;
  title: string;
}) {
  const mediaUrl = resolveMediaUrl(attachment.file_url);
  const isVideo = attachment.content_type.startsWith("video/");
  const isImage = attachment.content_type.startsWith("image/");

  async function openFile() {
    if (mediaUrl) {
      await Linking.openURL(mediaUrl);
    }
  }

  return (
    <Pressable
      accessibilityLabel={`Open ${title.toLowerCase()} ${attachment.original_file_name}`}
      accessibilityRole="button"
      onPress={() => void openFile()}
      style={({ pressed }) => [styles.item, pressed ? styles.itemPressed : null]}
    >
      {mediaUrl && isImage ? (
        <Image resizeMode="cover" source={{ uri: mediaUrl }} style={styles.preview} />
      ) : (
        <View style={styles.videoPreview}>
          {isVideo ? (
            <Play color={colors.primary} fill={colors.primary} size={28} />
          ) : (
            <FileText color={colors.primary} size={28} />
          )}
          <Text style={styles.videoLabel}>{isVideo ? "Video" : "File"}</Text>
        </View>
      )}
      <Text numberOfLines={1} style={styles.fileName}>
        {attachment.original_file_name}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  item: {
    width: 132,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
  },
  itemPressed: {
    opacity: 0.78,
  },
  preview: {
    width: "100%",
    height: 92,
    backgroundColor: colors.surface,
  },
  videoPreview: {
    width: "100%",
    height: 92,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    backgroundColor: colors.surface,
  },
  videoLabel: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  fileName: {
    color: colors.text,
    fontSize: 12,
    padding: spacing.sm,
  },
});
