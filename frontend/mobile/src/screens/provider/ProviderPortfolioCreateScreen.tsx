import * as ImagePicker from "expo-image-picker";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { ImagePlus, Play } from "lucide-react-native";
import { useState } from "react";
import {
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { createProviderPortfolio } from "../../api/provider";
import { PrimaryButton } from "../../components/PrimaryButton";
import { ScreenContainer } from "../../components/ScreenContainer";
import { TextField } from "../../components/TextField";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors, radius, spacing } from "../../theme/theme";
import { getErrorMessage } from "../../utils/errors";

export function ProviderPortfolioCreateScreen() {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assets, setAssets] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function handlePickMedia() {
    setMessage("");

    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setMessage("Allow access to photos to add portfolio media.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsMultipleSelection: true,
      mediaTypes: ["images", "videos"],
      quality: 0.85,
      videoQuality: ImagePicker.UIImagePickerControllerQualityType.Medium,
    });

    if (result.canceled || result.assets.length === 0) {
      return;
    }

    setAssets(result.assets);
  }

  async function handleSave() {
    const cleanTitle = title.trim();

    if (!cleanTitle || assets.length === 0) {
      setMessage("Add at least one file and a title.");
      return;
    }

    setIsSaving(true);
    setMessage("");

    try {
      await createProviderPortfolio({
        title: cleanTitle,
        description: description.trim() || null,
        mediaFiles: assets.map((asset) => ({
          uri: asset.uri,
          fileName: asset.fileName,
          mimeType: asset.mimeType,
        })),
      });
      navigation.goBack();
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  const previewAsset = assets[0] ?? null;
  const isVideo = previewAsset?.type === "video";

  return (
    <ScreenContainer contentStyle={styles.content}>
      <Pressable
        accessibilityRole="button"
        onPress={() => void handlePickMedia()}
        style={styles.mediaPicker}
      >
        {previewAsset && !isVideo ? (
          <Image source={{ uri: previewAsset.uri }} style={styles.previewImage} />
        ) : (
          <View style={[styles.placeholder, isVideo ? styles.videoPlaceholder : null]}>
            {isVideo ? (
              <Play color="#FFFFFF" fill="#FFFFFF" size={34} />
            ) : (
              <ImagePlus color={colors.mutedText} size={34} />
            )}
            <Text style={[styles.placeholderText, isVideo ? styles.videoText : null]}>
              {assets.length > 0
                ? `Selected ${assets.length} portfolio items`
                : isVideo
                  ? "Video selected"
                  : "Choose photo or video"}
            </Text>
          </View>
        )}
      </Pressable>
      {assets.length > 1 ? (
        <Text style={styles.selectedCountText}>
          Saved as one portfolio; swipe to browse
        </Text>
      ) : null}

      <View style={styles.card}>
        <TextField
          label="Title"
          onChangeText={setTitle}
          placeholder="Title"
          value={title}
        />
        <TextField
          label="Description"
          multiline
          numberOfLines={4}
          onChangeText={setDescription}
          placeholder="Description"
          value={description}
        />

        {message ? <Text style={styles.messageText}>{message}</Text> : null}

        <PrimaryButton
          disabled={isSaving}
          label={isSaving ? "Uploading..." : "Save portfolio"}
          onPress={() => void handleSave()}
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: colors.surface,
    paddingTop: spacing.lg,
  },
  mediaPicker: {
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: colors.background,
    aspectRatio: 1.5,
  },
  previewImage: {
    width: "100%",
    height: "100%",
  },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.surface,
  },
  videoPlaceholder: {
    backgroundColor: colors.text,
  },
  placeholderText: {
    color: colors.mutedText,
    fontSize: 15,
    fontWeight: "700",
  },
  videoText: {
    color: "#FFFFFF",
  },
  selectedCountText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  card: {
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  messageText: {
    color: colors.danger,
    fontSize: 13,
  },
});
