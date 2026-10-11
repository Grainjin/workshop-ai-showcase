import { Check, MapPin, X } from "lucide-react-native";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  getServiceLocationPath,
  getServiceLocations,
} from "../api/locations";
import {
  chooseCity,
  chooseDistrict,
  chooseProvince,
  EMPTY_LOCATION_CASCADE,
  getCompletedLocation,
  type LocationCascadeState,
} from "../features/locations/location-cascade-state";
import { colors, radius, spacing } from "../theme/theme";
import type {
  ServiceAreaSelection,
  ServiceLocation,
} from "../types/location";

type LocationCascadePickerModalProps = {
  visible: boolean;
  value: ServiceAreaSelection | null;
  onClose: () => void;
  onSelect: (selection: ServiceAreaSelection) => void;
  allowAnyLevel?: boolean;
};

export function LocationCascadePickerModal({
  visible,
  value,
  onClose,
  onSelect,
  allowAnyLevel = false,
}: LocationCascadePickerModalProps) {
  const [cascade, setCascade] = useState<LocationCascadeState>(
    EMPTY_LOCATION_CASCADE,
  );
  const [provinces, setProvinces] = useState<ServiceLocation[]>([]);
  const [cities, setCities] = useState<ServiceLocation[]>([]);
  const [districts, setDistricts] = useState<ServiceLocation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const completedLocation = useMemo(
    () => getCompletedLocation(cascade, allowAnyLevel),
    [allowAnyLevel, cascade],
  );

  useEffect(() => {
    if (!visible) {
      return;
    }

    let isActive = true;

    async function initialise() {
      setIsLoading(true);
      setMessage("");

      try {
        const nextProvinces = await getServiceLocations();
        if (!isActive) {
          return;
        }
        if (nextProvinces.length === 0) {
          throw new Error("No service areas were returned.");
        }
        setProvinces(nextProvinces);

        if (!value?.serviceLocationId) {
          setCascade(EMPTY_LOCATION_CASCADE);
          setCities([]);
          setDistricts([]);
          return;
        }

        const path = await getServiceLocationPath(value.serviceLocationId);
        const nextCities = await getServiceLocations(path.province.id);
        const nextDistricts = path.city
          ? await getServiceLocations(path.city.id)
          : [];
        if (!isActive) {
          return;
        }
        setCascade(path);
        setCities(nextCities);
        setDistricts(nextDistricts);
      } catch {
        if (isActive) {
          setMessage("Couldn't load service areas. Try again.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void initialise();

    return () => {
      isActive = false;
    };
  }, [reloadKey, value?.serviceLocationId, visible]);

  async function handleProvince(province: ServiceLocation) {
    setCascade((current) => chooseProvince(current, province));
    setCities([]);
    setDistricts([]);
    setMessage("");

    try {
      setCities(await getServiceLocations(province.id));
    } catch {
      setMessage("Couldn't load cities. Try again.");
    }
  }

  async function handleCity(city: ServiceLocation) {
    setCascade((current) => chooseCity(current, city));
    setDistricts([]);
    setMessage("");

    try {
      setDistricts(await getServiceLocations(city.id));
    } catch {
      setMessage("Couldn't load districts. Try again.");
    }
  }

  function handleDistrict(district: ServiceLocation) {
    setCascade((current) => chooseDistrict(current, district));
    setMessage("");
  }

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={visible}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={styles.titleRow}>
              <MapPin color={colors.primary} size={22} />
              <View>
                <Text style={styles.title}>Select service area</Text>
                <Text style={styles.subtitle}>Province / City / District</Text>
              </View>
            </View>
            <Pressable
              accessibilityLabel="Close service area picker"
              accessibilityRole="button"
              onPress={onClose}
              style={styles.iconButton}
            >
              <X color={colors.text} size={20} />
            </Pressable>
          </View>

          {isLoading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.loadingText}>Loading service areas...</Text>
            </View>
          ) : (
            <ScrollView contentContainerStyle={styles.content}>
              <LocationLevel
                label="Province"
                locations={provinces}
                onSelect={(location) => void handleProvince(location)}
                selectedId={cascade.province?.id ?? null}
              />
              <LocationLevel
                emptyText="Select a province first"
                label="City"
                locations={cities}
                onSelect={(location) => void handleCity(location)}
                selectedId={cascade.city?.id ?? null}
              />
              <LocationLevel
                emptyText="Select a city first"
                label="District"
                locations={districts}
                onSelect={handleDistrict}
                selectedId={cascade.district?.id ?? null}
              />
            </ScrollView>
          )}

          {message ? (
            <View style={styles.retryRow}>
              <Text style={styles.errorText}>{message}</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => setReloadKey((current) => current + 1)}
                style={styles.retryButton}
              >
                <Text style={styles.retryButtonText}>Retry</Text>
              </Pressable>
            </View>
          ) : null}

          <Pressable
            accessibilityRole="button"
            disabled={!completedLocation}
            onPress={() => completedLocation && onSelect(completedLocation)}
            style={[
              styles.confirmButton,
              !completedLocation ? styles.confirmButtonDisabled : null,
            ]}
          >
            <Text style={styles.confirmButtonText}>
              {completedLocation
                ? `Use ${completedLocation.label}`
                : allowAnyLevel
                  ? "Choose a province, city, or district"
                  : "Choose a district"}
            </Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function LocationLevel({
  label,
  locations,
  selectedId,
  onSelect,
  emptyText = "No options available",
}: {
  label: string;
  locations: ServiceLocation[];
  selectedId: number | null;
  onSelect: (location: ServiceLocation) => void;
  emptyText?: string;
}) {
  return (
    <View style={styles.level}>
      <Text style={styles.levelLabel}>{label}</Text>
      {locations.length > 0 ? (
        <View style={styles.optionGrid}>
          {locations.map((location) => {
            const isSelected = location.id === selectedId;

            return (
              <Pressable
                accessibilityRole="button"
                key={location.id}
                onPress={() => onSelect(location)}
                style={[styles.option, isSelected ? styles.optionSelected : null]}
              >
                <Text
                  style={[
                    styles.optionText,
                    isSelected ? styles.optionTextSelected : null,
                  ]}
                >
                  {location.name}
                </Text>
                {isSelected ? <Check color={colors.primary} size={16} /> : null}
              </Pressable>
            );
          })}
        </View>
      ) : (
        <Text style={styles.emptyText}>{emptyText}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0, 0, 0, 0.18)",
  },
  sheet: {
    maxHeight: "90%",
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    backgroundColor: colors.background,
    padding: spacing.lg,
    gap: spacing.md,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
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
  },
  iconButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.surface,
  },
  loadingBox: {
    minHeight: 260,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  loadingText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  content: {
    gap: spacing.lg,
    paddingBottom: spacing.sm,
  },
  level: {
    gap: spacing.sm,
  },
  levelLabel: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
  },
  optionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  option: {
    minHeight: 40,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
  },
  optionSelected: {
    borderColor: colors.primary,
    backgroundColor: "#E9F7F3",
  },
  optionText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  optionTextSelected: {
    color: colors.primary,
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  errorText: {
    color: colors.danger,
    flex: 1,
    fontSize: 13,
  },
  retryRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  retryButton: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  retryButtonText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "700",
  },
  confirmButton: {
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
  },
  confirmButtonDisabled: {
    opacity: 0.45,
  },
  confirmButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
    textAlign: "center",
  },
});
