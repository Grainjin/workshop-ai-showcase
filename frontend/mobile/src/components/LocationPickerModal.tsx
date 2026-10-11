import * as Location from "expo-location";
import { LocateFixed, MapPin, X } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { getPlaceDetails, searchPlaces } from "../api/places";
import { colors, radius, spacing } from "../theme/theme";
import type { PlaceSuggestion, SelectedLocation } from "../types/location";
import { getErrorMessage } from "../utils/errors";
import { PrimaryButton } from "./PrimaryButton";
import { SecondaryButton } from "./SecondaryButton";

/**
 * One picker for web, iOS and Android, backed only by our /places
 * proxy — no Google script, no window.google, no platform fork.
 *
 * Coordinates can no longer be typed: they come from a chosen suggestion or
 * from the device, so a saved location always has a real point on the map.
 */
type LocationPickerModalProps = {
  visible: boolean;
  value: SelectedLocation | null;
  onClose: () => void;
  onConfirm: (location: SelectedLocation) => void;
};

const SEARCH_DEBOUNCE_MS = 350;
const MAX_SUGGESTIONS = 5;

export function LocationPickerModal({
  visible,
  value,
  onClose,
  onConfirm,
}: LocationPickerModalProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [selected, setSelected] = useState<SelectedLocation | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Typing fires a request per keystroke otherwise, and the proxy is rate
  // limited. Only the newest search is allowed to land.
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!visible) {
      return;
    }

    setQuery(value?.label ?? "");
    setSelected(value ?? null);
    setSuggestions([]);
    setErrorMessage("");
  }, [visible, value]);

  useEffect(() => {
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
      searchController.current?.abort();
    };
  }, []);

  function handleQueryChange(nextQuery: string) {
    setQuery(nextQuery);
    setErrorMessage("");

    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchController.current?.abort();

    const trimmed = nextQuery.trim();
    if (!trimmed) {
      setSuggestions([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimer.current = setTimeout(() => {
      const controller = new AbortController();
      searchController.current = controller;

      searchPlaces(trimmed, controller.signal)
        .then((results) => {
          setSuggestions(results.slice(0, MAX_SUGGESTIONS));
          setIsSearching(false);
        })
        .catch((error) => {
          if (controller.signal.aborted) {
            return;
          }

          setSuggestions([]);
          setIsSearching(false);
          setErrorMessage(getErrorMessage(error));
        });
    }, SEARCH_DEBOUNCE_MS);
  }

  async function handleSelectSuggestion(suggestion: PlaceSuggestion) {
    setIsResolving(true);
    setErrorMessage("");

    try {
      const details = await getPlaceDetails(suggestion.place_id);

      if (!details) {
        setErrorMessage("Could not read this address. Try another one.");
        return;
      }

      setSelected({
        label: details.formatted_address || suggestion.description,
        latitude: details.latitude,
        longitude: details.longitude,
        placeId: details.place_id,
      });
      setQuery(details.formatted_address || suggestion.description);
      setSuggestions([]);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsResolving(false);
    }
  }

  async function useCurrentLocation() {
    setErrorMessage("");
    setIsLocating(true);

    try {
      const permission = await Location.requestForegroundPermissionsAsync();

      if (permission.status !== "granted") {
        setErrorMessage("Location access denied. Search for the address instead.");
        return;
      }

      const currentLocation = await Location.getCurrentPositionAsync({});
      setSelected({
        label: "Current location",
        latitude: currentLocation.coords.latitude,
        longitude: currentLocation.coords.longitude,
        placeId: null,
      });
      setQuery("Current location");
      setSuggestions([]);
    } catch {
      setErrorMessage("Could not get your location. Search for the address instead.");
    } finally {
      setIsLocating(false);
    }
  }

  function handleConfirm() {
    if (!selected) {
      setErrorMessage("Pick a suggestion or use your current location.");
      return;
    }

    onConfirm(selected);
  }

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={visible}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View>
              <Text style={styles.title}>Select service location</Text>
              <Text style={styles.subtitle}>Filter nearby available providers</Text>
            </View>
            <Pressable
              accessibilityLabel="Close location picker"
              accessibilityRole="button"
              onPress={onClose}
              style={styles.iconButton}
            >
              <X color={colors.text} size={20} />
            </Pressable>
          </View>

          <View style={styles.preview}>
            <MapPin color={colors.primary} size={34} />
            <Text style={styles.previewTitle}>
              {selected?.label ?? "No location selected"}
            </Text>
            <Text style={styles.previewText}>
              {selected
                ? `${selected.latitude.toFixed(6)}, ${selected.longitude.toFixed(6)}`
                : "Search for an address or use your current location"}
            </Text>
          </View>

          <View style={styles.form}>
            <Text style={styles.label}>Address</Text>
            <TextInput
              autoCorrect={false}
              onChangeText={handleQueryChange}
              placeholder="Start typing an address"
              placeholderTextColor={colors.mutedText}
              style={styles.input}
              value={query}
            />

            {isSearching || isResolving ? (
              <View style={styles.searchingRow}>
                <ActivityIndicator color={colors.primary} size="small" />
                <Text style={styles.searchingText}>
                  {isResolving ? "Reading the address…" : "Searching…"}
                </Text>
              </View>
            ) : null}

            {suggestions.length > 0 ? (
              <ScrollView
                keyboardShouldPersistTaps="handled"
                style={styles.suggestionList}
              >
                {suggestions.map((suggestion) => (
                  <Pressable
                    accessibilityRole="button"
                    key={suggestion.place_id}
                    onPress={() => void handleSelectSuggestion(suggestion)}
                    style={({ pressed }) => [
                      styles.suggestionItem,
                      pressed ? styles.suggestionItemPressed : null,
                    ]}
                  >
                    <MapPin color={colors.mutedText} size={16} />
                    <Text style={styles.suggestionText}>{suggestion.description}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : null}

            {errorMessage ? (
              <Text style={styles.errorText}>{errorMessage}</Text>
            ) : null}
          </View>

          <View style={styles.actions}>
            <SecondaryButton
              disabled={isLocating}
              label={isLocating ? "Locating…" : "Use current location"}
              onPress={() => void useCurrentLocation()}
            />
            <PrimaryButton
              disabled={!selected}
              label="Confirm location"
              onPress={handleConfirm}
            />
          </View>

          <View style={styles.hintRow}>
            <LocateFixed color={colors.mutedText} size={14} />
            <Text style={styles.hintText}>
              Addresses come from the Workshop AI places service, so the map point
              is always exact.
            </Text>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  sheet: {
    gap: spacing.md,
    borderTopLeftRadius: radius.md,
    borderTopRightRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
    maxHeight: "90%",
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    color: colors.mutedText,
    fontSize: 13,
    marginTop: 2,
  },
  iconButton: {
    padding: spacing.xs,
  },
  preview: {
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  previewTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  previewText: {
    color: colors.mutedText,
    fontSize: 13,
    textAlign: "center",
  },
  form: {
    gap: spacing.sm,
  },
  label: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    color: colors.text,
    fontSize: 15,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  searchingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  searchingText: {
    color: colors.mutedText,
    fontSize: 13,
  },
  suggestionList: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    maxHeight: 220,
  },
  suggestionItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  suggestionItemPressed: {
    backgroundColor: colors.surface,
  },
  suggestionText: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
  },
  errorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  actions: {
    gap: spacing.sm,
  },
  hintRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.xs,
  },
  hintText: {
    color: colors.mutedText,
    flex: 1,
    fontSize: 12,
    lineHeight: 17,
  },
});
