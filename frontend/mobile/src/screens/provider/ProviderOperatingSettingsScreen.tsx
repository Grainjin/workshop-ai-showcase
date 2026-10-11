import { useFocusEffect } from "@react-navigation/native";
import { MapPin, Trash2 } from "lucide-react-native";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  getApprovedServices,
  getProviderProfile,
  getProviderServiceAreas,
  updateProviderOperatingSettings,
  updateProviderServiceAreas,
} from "../../api/provider";
import { LocationCascadePickerModal } from "../../components/LocationCascadePickerModal";
import { LocationPickerModal } from "../../components/LocationPickerModal";
import { PrimaryButton } from "../../components/PrimaryButton";
import { TextField } from "../../components/TextField";
import { getProviderTagLabel } from "../../constants/providerTags";
import { colors, radius, spacing } from "../../theme/theme";
import type { SelectedLocation, ServiceAreaSelection } from "../../types/location";
import type { ApprovedServices, ProviderProfile, ProviderServiceArea } from "../../types/provider";
import { getErrorMessage } from "../../utils/errors";

export function ProviderOperatingSettingsScreen() {
  const [profile, setProfile] = useState<ProviderProfile | null>(null);
  const [services, setServices] = useState<ApprovedServices | null>(null);
  const [areas, setAreas] = useState<ProviderServiceArea[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [nextProfile, nextServices, nextAreas] = await Promise.all([
        getProviderProfile(),
        getApprovedServices(),
        getProviderServiceAreas(),
      ]);
      setProfile(nextProfile);
      setServices(nextServices);
      setAreas(nextAreas?.service_areas ?? []);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => void load(), [load]));

  if (isLoading) {
    return <ActivityIndicator color={colors.primary} style={styles.loader} />;
  }

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {profile && services ? (
        <OperatingSettingsForm
          approvedServices={services}
          initialAreas={areas}
          onSaved={() => void load()}
          profile={profile}
        />
      ) : null}
    </ScrollView>
  );
}

function OperatingSettingsForm({
  approvedServices,
  initialAreas,
  onSaved,
  profile,
}: {
  approvedServices: ApprovedServices;
  initialAreas: ProviderServiceArea[];
  onSaved: () => void;
  profile: ProviderProfile;
}) {
  const [description, setDescription] = useState(profile.bio);
  const [phone, setPhone] = useState(profile.phone_number);
  const [hourlyRate, setHourlyRate] = useState(String(profile.hourly_rate));
  const [address, setAddress] = useState<SelectedLocation | null>(
    profile.latitude != null && profile.longitude != null
      ? {
          label: profile.address,
          latitude: profile.latitude,
          longitude: profile.longitude,
          placeId: profile.business_place_id ?? null,
        }
      : null,
  );
  const [enabledServices, setEnabledServices] = useState(
    approvedServices.enabled_service_categories,
  );
  const [areas, setAreas] = useState(initialAreas);
  const [showAddressPicker, setShowAddressPicker] = useState(false);
  const [showAreaPicker, setShowAreaPicker] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    const rate = Number(hourlyRate);
    if (
      !description.trim() ||
      !phone.trim() ||
      !address ||
      !Number.isFinite(rate) ||
      rate <= 0
    ) {
      setError("Complete all operating settings and enter a valid hourly rate.");
      return;
    }
    if (areas.length === 0) {
      setError("Add at least one service area.");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await updateProviderOperatingSettings({
        description: description.trim(),
        contact_phone: phone.trim(),
        business_address: address.label,
        business_place_id: address.placeId,
        business_latitude: address.latitude,
        business_longitude: address.longitude,
        hourly_rate: rate,
        enabled_service_categories: enabledServices,
      });
      await updateProviderServiceAreas(areas.map((area) => area.id));
      Alert.alert("Saved", "Your operating settings have been updated.");
      onSaved();
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setIsSaving(false);
    }
  }

  function addArea(selection: ServiceAreaSelection) {
    if (!areas.some((area) => area.id === selection.serviceLocationId)) {
      const depth = selection.label.split(" / ").length;
      setAreas((current) => [
        ...current,
        {
          id: selection.serviceLocationId,
          name: selection.label,
          label: selection.label,
          serviceProvince: selection.serviceProvince,
          level:
            depth === 1 ? "province" : depth === 2 ? "city" : "district",
        },
      ]);
    }
    setShowAreaPicker(false);
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Operating settings</Text>
      <Text style={styles.hint}>
        Manage day-to-day business information after service verification.
        These changes do not alter the approved application record.
      </Text>
      <TextField
        label="Business description"
        multiline
        onChangeText={setDescription}
        value={description}
      />
      <TextField
        label="Contact phone"
        keyboardType="phone-pad"
        onChangeText={setPhone}
        value={phone}
      />
      <TextField
        label="Hourly rate"
        keyboardType="numeric"
        onChangeText={setHourlyRate}
        value={hourlyRate}
      />

      <Text style={styles.label}>Business address</Text>
      <Pressable
        onPress={() => setShowAddressPicker(true)}
        style={styles.selectionRow}
      >
        <MapPin color={colors.primary} size={20} />
        <Text style={styles.flex}>
          {address?.label || "Select the exact business address"}
        </Text>
      </Pressable>

      <Text style={styles.label}>Enabled services</Text>
      <Text style={styles.hint}>Only Admin-approved services can be enabled.</Text>
      <View style={styles.tags}>
        {approvedServices.approved_service_categories.map((service) => {
          const active = enabledServices.includes(service);
          return (
            <Pressable
              key={service}
              onPress={() =>
                setEnabledServices(
                  active
                    ? enabledServices.filter((item) => item !== service)
                    : [...enabledServices, service],
                )
              }
              style={[styles.tag, active ? styles.tagActive : null]}
            >
              <Text style={[styles.tagText, active ? styles.tagTextActive : null]}>
                {getProviderTagLabel(service)}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.label}>Service areas</Text>
        <Pressable onPress={() => setShowAreaPicker(true)}>
          <Text style={styles.link}>Add area</Text>
        </Pressable>
      </View>
      {areas.map((area) => (
        <View key={area.id} style={styles.selectionRow}>
          <MapPin color={colors.primary} size={18} />
          <Text style={styles.flex}>{area.label ?? area.name}</Text>
          <Pressable
            onPress={() =>
              setAreas((current) => current.filter((item) => item.id !== area.id))
            }
          >
            <Trash2 color={colors.danger} size={18} />
          </Pressable>
        </View>
      ))}

      {error ? <Text style={styles.error}>{error}</Text> : null}
      <PrimaryButton
        isLoading={isSaving}
        label="Save operating settings"
        onPress={() => void save()}
      />

      <LocationPickerModal
        onClose={() => setShowAddressPicker(false)}
        onConfirm={(location) => {
          setAddress(location);
          setShowAddressPicker(false);
        }}
        value={address}
        visible={showAddressPicker}
      />
      <LocationCascadePickerModal
        allowAnyLevel
        onClose={() => setShowAreaPicker(false)}
        onSelect={addArea}
        value={null}
        visible={showAreaPicker}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  content: {
    width: "100%",
    maxWidth: 820,
    alignSelf: "center",
    padding: spacing.lg,
  },
  loader: { flex: 1 },
  card: {
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  title: { color: colors.text, fontSize: 24, fontWeight: "800" },
  label: { color: colors.text, fontSize: 14, fontWeight: "700" },
  hint: { color: colors.mutedText, fontSize: 13, lineHeight: 19 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 20 },
  selectionRow: {
    minHeight: 50,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tag: {
    minHeight: 40,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
  },
  tagActive: { borderColor: colors.primary, backgroundColor: "#E9F7F3" },
  tagText: { color: colors.text, fontWeight: "600" },
  tagTextActive: { color: colors.primary },
  link: { color: colors.primary, fontWeight: "700" },
  flex: { flex: 1, color: colors.text },
});
