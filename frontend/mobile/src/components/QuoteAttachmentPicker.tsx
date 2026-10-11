import * as DocumentPicker from "expo-document-picker";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { SecondaryButton } from "./SecondaryButton";
import { colors, spacing } from "../theme/theme";
import type { BookingUploadFile } from "../types/booking";
import { getErrorMessage } from "../utils/errors";

export function QuoteAttachmentPicker({ files, onChange, disabled, error = "" }: {
  files: BookingUploadFile[];
  onChange: (files: BookingUploadFile[]) => void;
  disabled: boolean;
  error?: string;
}) {
  const [pickerError, setPickerError] = useState("");
  async function pickFiles() {
    setPickerError("");
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ["image/*", "video/*", "application/pdf"],
        multiple: true,
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;
      if (result.assets.some((asset) => !/\.(jpe?g|png|pdf|mp4|mov)$/i.test(asset.name))) {
        setPickerError("Use JPG, PNG, PDF, MP4 or MOV files.");
        return;
      }
      onChange([...files, ...result.assets.map((asset) => ({
        uri: asset.uri, fileName: asset.name,
        mimeType: asset.mimeType || "application/octet-stream", size: asset.size,
      }))]);
    } catch (cause) {
      setPickerError(getErrorMessage(cause));
    }
  }
  return (
    <View style={styles.section}>
      <Text style={styles.label}>Quote attachments (optional)</Text>
      {files.map((file, index) => (
        <View key={`${file.uri}-${index}`} style={styles.row}>
          <Text numberOfLines={1} style={styles.name}>{file.fileName}</Text>
          <Pressable accessibilityLabel={`Remove ${file.fileName}`} accessibilityRole="button" disabled={disabled} onPress={() => onChange(files.filter((_, item) => item !== index))}>
            <Text style={styles.remove}>Remove</Text>
          </Pressable>
        </View>
      ))}
      <SecondaryButton disabled={disabled} label="Add attachments" onPress={() => void pickFiles()} />
      {error || pickerError ? <Text style={styles.error}>{error || pickerError}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: { gap: spacing.sm },
  label: { color: colors.mutedText, fontSize: 13, fontWeight: "700" },
  row: { alignItems: "center", flexDirection: "row", gap: spacing.sm },
  name: { color: colors.text, flex: 1, fontSize: 13 },
  remove: { color: colors.mutedText, fontSize: 13 },
  error: { color: colors.danger, fontSize: 13 },
});
