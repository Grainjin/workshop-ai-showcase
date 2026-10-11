import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { getProviderTagLabel } from "../constants/providerTags";
import { colors, spacing } from "../theme/theme";
import type { BookingPayload, BookingUploadFile } from "../types/booking";
import type { ProviderProfile } from "../types/provider";
import { formatDateTimeInput } from "../utils/datetime";
import {
  getDefaultServiceCategory,
  isCanonicalServiceSelection,
} from "../utils/bookingService";
import { DateTimeField } from "./DateTimeField";
import { PrimaryButton } from "./PrimaryButton";
import { SecondaryButton } from "./SecondaryButton";
import { TextField } from "./TextField";

export type BookingRequestFormState = {
  title: string;
  serviceCategory: string;
  serviceDescription: string;
  serviceAddress: string;
  scheduledStartTime: string;
  scheduledEndTime: string;
  attachments: BookingUploadFile[];
};

type BookingRequestModalProps = {
  visible: boolean;
  bookingForm: BookingRequestFormState;
  errorMessage: string;
  isLoading: boolean;
  serviceCategories: string[];
  onClose: () => void;
  onSubmit: () => void;
  setBookingForm: (value: BookingRequestFormState) => void;
};

const ISTANBUL_LOCATION = {
  latitude: 41.0082,
  longitude: 28.9784,
};

export function BookingRequestModal({
  visible,
  bookingForm,
  errorMessage,
  isLoading,
  serviceCategories,
  onClose,
  onSubmit,
  setBookingForm,
}: BookingRequestModalProps) {
  const [fileError, setFileError] = useState("");

  function updateFormField(field: keyof BookingRequestFormState, value: string) {
    setBookingForm({
      ...bookingForm,
      [field]: value,
    });
  }

  async function pickAttachments() {
    setFileError("");
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setFileError("Allow access to photos and videos to add attachments.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsMultipleSelection: true,
      mediaTypes: ["images", "videos"],
      quality: 0.85,
      videoQuality: ImagePicker.UIImagePickerControllerQualityType.Medium,
    });
    if (result.canceled) return;

    const nextFiles: BookingUploadFile[] = result.assets.map((asset, index) => ({
      uri: asset.uri,
      fileName: asset.fileName || `booking-attachment-${index + 1}`,
      mimeType: asset.mimeType || (asset.type === "video" ? "video/mp4" : "image/jpeg"),
      size: asset.fileSize,
    }));
    const combined = [...bookingForm.attachments, ...nextFiles];
    const images = combined.filter((file) => file.mimeType.startsWith("image/"));
    const videos = combined.filter((file) => file.mimeType.startsWith("video/"));
    if (combined.length > 7 || images.length > 5 || videos.length > 2) {
      setFileError("Attach up to 5 images and 2 videos (7 files total).");
      return;
    }
    const oversized = combined.find((file) => {
      if (file.size == null) return false;
      return file.mimeType.startsWith("video/")
        ? file.size > 10 * 1024 * 1024
        : file.size > 2 * 1024 * 1024;
    });
    if (oversized) {
      setFileError("Images must be 2 MB or less; videos must be 10 MB or less.");
      return;
    }
    setBookingForm({ ...bookingForm, attachments: combined });
  }

  return (
    <Modal
      animationType="slide"
      onRequestClose={onClose}
      transparent
      visible={visible}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Request booking</Text>
          <ScrollView contentContainerStyle={styles.modalScrollContent}>
            {errorMessage ? (
              <Text style={styles.modalErrorText}>{errorMessage}</Text>
            ) : null}
            <TextField
              label="Booking title"
              onChangeText={(value) => updateFormField("title", value)}
              placeholder="e.g. Kitchen pipe repair"
              value={bookingForm.title}
            />
            <Text style={styles.hint}>Maximum 30 words.</Text>
            <View style={styles.serviceField}>
              <Text style={styles.serviceLabel}>Service</Text>
              <View style={styles.serviceOptions}>
                {serviceCategories.map((category) => {
                  const selected = bookingForm.serviceCategory === category;
                  return (
                    <Pressable
                      accessibilityRole="button"
                      key={category}
                      onPress={() => updateFormField("serviceCategory", category)}
                      style={[styles.serviceOption, selected ? styles.serviceOptionSelected : null]}
                    >
                      <Text style={[styles.serviceOptionText, selected ? styles.serviceOptionTextSelected : null]}>
                        {getProviderTagLabel(category)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
            <TextField
              label="Service description"
              multiline
              numberOfLines={3}
              onChangeText={(value) => updateFormField("serviceDescription", value)}
              placeholder="e.g. Kitchen pipe leak"
              value={bookingForm.serviceDescription}
            />
            <TextField
              label="Service address"
              onChangeText={(value) => updateFormField("serviceAddress", value)}
              placeholder="Address"
              value={bookingForm.serviceAddress}
            />
            <DateTimeField
              label="Start time"
              onChange={(value) => updateFormField("scheduledStartTime", value)}
              value={bookingForm.scheduledStartTime}
            />
            <DateTimeField
              label="End time"
              onChange={(value) => updateFormField("scheduledEndTime", value)}
              value={bookingForm.scheduledEndTime}
            />
            <View style={styles.attachmentBox}>
              <Text style={styles.attachmentTitle}>Attachments (optional)</Text>
              <Text style={styles.hint}>Up to 5 images (2 MB each) and 2 videos (10 MB each).</Text>
              {bookingForm.attachments.map((file, index) => (
                <View key={`${file.uri}-${index}`} style={styles.fileRow}>
                  <Text numberOfLines={1} style={styles.fileName}>{file.fileName}</Text>
                  <SecondaryButton
                    label="Remove"
                    onPress={() => setBookingForm({
                      ...bookingForm,
                      attachments: bookingForm.attachments.filter((_, itemIndex) => itemIndex !== index),
                    })}
                  />
                </View>
              ))}
              <SecondaryButton
                disabled={bookingForm.attachments.length >= 7}
                label="Add photos or videos"
                onPress={() => void pickAttachments()}
              />
              {fileError ? <Text style={styles.modalErrorText}>{fileError}</Text> : null}
            </View>
          </ScrollView>
          <View style={styles.modalActions}>
            <SecondaryButton disabled={isLoading} label="Cancel" onPress={onClose} />
            <PrimaryButton
              disabled={isLoading}
              isLoading={isLoading}
              label="Send request"
              onPress={onSubmit}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

export function createDefaultBookingRequestForm(
  provider?: ProviderProfile | null,
): BookingRequestFormState {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(10, 0, 0, 0);

  const end = new Date(start);
  end.setHours(12, 0, 0, 0);

  return {
    title: "",
    serviceCategory: getDefaultServiceCategory(provider?.tags ?? []),
    serviceDescription: "",
    serviceAddress: provider?.address || "Istanbul",
    scheduledStartTime: formatDateTimeInput(start),
    scheduledEndTime: formatDateTimeInput(end),
    attachments: [],
  };
}

export function buildBookingRequestPayload({
  provider,
  providerProfileId,
  chatRoomId,
  form,
}: {
  provider?: ProviderProfile | null;
  providerProfileId: number;
  chatRoomId?: number | null;
  form: BookingRequestFormState;
}): BookingPayload | null {
  if (
    !form.title.trim() ||
    form.title.trim().split(/\s+/).length > 30 ||
    !form.serviceDescription.trim() ||
    !form.serviceAddress.trim() ||
    !form.scheduledStartTime.trim() ||
    !form.scheduledEndTime.trim() ||
    !isCanonicalServiceSelection(form.serviceCategory, provider?.tags ?? [])
  ) {
    return null;
  }

  return {
    provider_profile_id: providerProfileId,
    chat_room_id: chatRoomId ?? null,
    service_category: form.serviceCategory,
    title: form.title.trim(),
    service_description: form.serviceDescription.trim(),
    service_address: form.serviceAddress.trim(),
    service_latitude: provider?.latitude ?? ISTANBUL_LOCATION.latitude,
    service_longitude: provider?.longitude ?? ISTANBUL_LOCATION.longitude,
    customer_current_address: null,
    customer_current_latitude: null,
    customer_current_longitude: null,
    scheduled_start_time: form.scheduledStartTime.trim(),
    scheduled_end_time: form.scheduledEndTime.trim(),
    attachments: form.attachments,
  };
}

const styles = StyleSheet.create({
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
  modalErrorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 19,
  },
  modalScrollContent: {
    gap: spacing.md,
    paddingBottom: spacing.sm,
  },
  hint: {
    color: colors.mutedText,
    fontSize: 12,
  },
  serviceField: {
    gap: spacing.sm,
  },
  serviceLabel: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  serviceOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  serviceOption: {
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  serviceOptionSelected: {
    backgroundColor: colors.surface,
    borderColor: colors.primary,
  },
  serviceOptionText: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
  },
  serviceOptionTextSelected: {
    color: colors.primary,
  },
  attachmentBox: {
    gap: spacing.sm,
  },
  attachmentTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  fileRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  fileName: {
    flex: 1,
    color: colors.text,
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: spacing.md,
  },
});
