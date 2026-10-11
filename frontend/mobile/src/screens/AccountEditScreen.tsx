import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { ChevronDown } from "lucide-react-native";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getCustomerProfile, patchCustomerProfile } from "../api/customer";
import { getProviderVerificationStatus } from "../api/provider";
import { PrimaryButton } from "../components/PrimaryButton";
import { LocationCascadePickerModal } from "../components/LocationCascadePickerModal";
import { ScreenContainer } from "../components/ScreenContainer";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { colors, radius, spacing } from "../theme/theme";
import type { ServiceAreaSelection } from "../types/location";

const DEFAULT_SERVICE_PROVINCE = "Istanbul";

type AccountFormValues = {
  firstName: string;
  lastName: string;
  phoneNumber: string;
  address: string;
  serviceProvince: string;
  serviceLocationId: number | null;
  notes: string;
};

type MessageTone = "success" | "error";

/**
 * users.name stays the joined display string, so the two fields are
 * split from it whenever the API has not sent them separately yet.
 */
function splitDisplayName(user: { name: string; first_name?: string | null; last_name?: string | null }) {
  if (user.first_name || user.last_name) {
    return {
      firstName: user.first_name ?? "",
      lastName: user.last_name ?? "",
    };
  }

  const trimmed = (user.name ?? "").trim();
  const firstSpace = trimmed.indexOf(" ");

  if (firstSpace === -1) {
    return { firstName: trimmed, lastName: "" };
  }

  return {
    firstName: trimmed.slice(0, firstSpace),
    lastName: trimmed.slice(firstSpace + 1).trim(),
  };
}

function toFormValues(
  user: { name: string; first_name?: string | null; last_name?: string | null },
  profile?: {
    phone_number?: string | null;
    address?: string | null;
    service_province?: string | null;
    service_location_id?: number | null;
    notes?: string | null;
  } | null,
): AccountFormValues {
  return {
    ...splitDisplayName(user),
    phoneNumber: profile?.phone_number ?? "",
    address: profile?.address ?? "",
    serviceProvince: profile?.service_province || DEFAULT_SERVICE_PROVINCE,
    serviceLocationId: profile?.service_location_id ?? null,
    notes: profile?.notes ?? "",
  };
}

export function AccountEditScreen() {
  const { user, patchUserProfile } = useAuth();
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [firstName, setFirstName] = useState(
    user ? splitDisplayName(user).firstName : "",
  );
  const [lastName, setLastName] = useState(
    user ? splitDisplayName(user).lastName : "",
  );
  const [phoneNumber, setPhoneNumber] = useState("");
  const [address, setAddress] = useState("");
  const [serviceProvince, setServiceProvince] = useState(
    DEFAULT_SERVICE_PROVINCE,
  );
  const [serviceLocationId, setServiceLocationId] = useState<number | null>(null);
  const [serviceAreaLabel, setServiceAreaLabel] = useState(
    DEFAULT_SERVICE_PROVINCE,
  );
  const [notes, setNotes] = useState("");
  const [isProvincePickerVisible, setIsProvincePickerVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<MessageTone>("success");
  const [providerIdentityStatus, setProviderIdentityStatus] = useState(
    user?.identity_verification_status ?? "not_submitted",
  );
  const [initialValues, setInitialValues] = useState<AccountFormValues | null>(
    user ? toFormValues(user) : null,
  );

  useFocusEffect(
    useCallback(() => {
      let isActive = true;

      async function loadProfile() {
        if (!user) {
          return;
        }

        setIsLoading(true);
        setMessage("");
        const fallbackValues = toFormValues(user);
        setFirstName(fallbackValues.firstName);
        setLastName(fallbackValues.lastName);
        setPhoneNumber(fallbackValues.phoneNumber);
        setAddress(fallbackValues.address);
        setServiceProvince(fallbackValues.serviceProvince);
        setServiceLocationId(fallbackValues.serviceLocationId);
        setServiceAreaLabel(fallbackValues.serviceProvince);
        setNotes(fallbackValues.notes);
        setInitialValues(fallbackValues);

        try {
          if (user.role === "customer") {
            const profile = await getCustomerProfile();

            if (isActive && profile) {
              const nextValues = toFormValues(user, profile);
              setPhoneNumber(nextValues.phoneNumber);
              setAddress(nextValues.address);
              setServiceProvince(nextValues.serviceProvince);
              setServiceLocationId(nextValues.serviceLocationId);
              setServiceAreaLabel(nextValues.serviceProvince);
              setNotes(nextValues.notes);
              setInitialValues(nextValues);
            }
          }

          if (user.role === "provider") {
            const verification = await getProviderVerificationStatus();
            if (isActive && verification) {
              setProviderIdentityStatus(verification.identity_status);
            }
          }

        } catch {
          if (isActive) {
            setServiceProvince(DEFAULT_SERVICE_PROVINCE);
            setServiceLocationId(null);
            setServiceAreaLabel(DEFAULT_SERVICE_PROVINCE);
          }
        } finally {
          if (isActive) {
            setIsLoading(false);
          }
        }
      }

      void loadProfile();

      return () => {
        isActive = false;
      };
    }, [user]),
  );

  async function handleSave() {
    if (!user || isSaving) {
      return;
    }

    const trimmedFirstName = firstName.trim();
    const trimmedLastName = lastName.trim();
    const trimmedPhone = phoneNumber.trim();
    const trimmedAddress = address.trim();
    const trimmedNotes = notes.trim();
    const currentValues = {
      firstName: trimmedFirstName,
      lastName: trimmedLastName,
      phoneNumber: trimmedPhone,
      address: trimmedAddress,
      serviceProvince,
      serviceLocationId,
      notes: trimmedNotes,
    };
    const savedValues = initialValues ?? toFormValues(user);
    const phoneChanged =
      currentValues.phoneNumber !== savedValues.phoneNumber.trim();
    const addressChanged = currentValues.address !== savedValues.address.trim();
    const profilePatch: Parameters<typeof patchCustomerProfile>[0] = {};

    if (phoneChanged) {
      profilePatch.phone_number = currentValues.phoneNumber;
    }
    if (addressChanged) {
      profilePatch.address = currentValues.address;
    }
    if (
      currentValues.serviceProvince !== savedValues.serviceProvince ||
      currentValues.serviceLocationId !== savedValues.serviceLocationId
    ) {
      profilePatch.service_province = currentValues.serviceProvince;
      profilePatch.service_location_id = currentValues.serviceLocationId;
    }
    if (currentValues.notes !== savedValues.notes.trim()) {
      profilePatch.notes = currentValues.notes || null;
    }
    const hasProfilePatch = Object.keys(profilePatch).length > 0;

    if (
      !trimmedFirstName ||
      !trimmedLastName ||
      (user.role === "customer" &&
        ((phoneChanged && !trimmedPhone) ||
          (addressChanged && !trimmedAddress)))
    ) {
      setMessageTone("error");
      setMessage("Fill in the required fields.");
      return;
    }

    setIsSaving(true);
    setMessage("");

    try {
      const nameChanged =
        currentValues.firstName !== savedValues.firstName.trim() ||
        currentValues.lastName !== savedValues.lastName.trim();

      if (nameChanged) {
        // The split-name API accepts these fields and rejects a payload that carries
        // both them and name. Name-only profiles use the compatibility payload.
        // Send whichever shape this backend understands.
        const supportsSplitNames =
          user.first_name !== undefined || user.last_name !== undefined;

        await patchUserProfile(
          supportsSplitNames
            ? {
                first_name: currentValues.firstName,
                last_name: currentValues.lastName,
              }
            : {
                name: `${currentValues.firstName} ${currentValues.lastName}`.trim(),
              },
        );
      }

      if (user.role === "customer") {
        if (hasProfilePatch) {
          await patchCustomerProfile(profilePatch);
        }
      }

      setMessageTone("success");
      setMessage("Profile saved");
      navigation.goBack();
    } catch {
      setMessageTone("error");
      setMessage("Couldn't save. Try again.");
    } finally {
      setIsSaving(false);
    }
  }

  const isProviderNameLocked =
    user?.role === "provider" &&
    ["pending", "approved"].includes(providerIdentityStatus);

  return (
    <ScreenContainer contentStyle={styles.content}>
      <View style={styles.card}>
        {isLoading ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : (
          <>
            <TextField
              autoCapitalize="words"
              editable={!isProviderNameLocked}
              label="First name"
              onChangeText={setFirstName}
              placeholder="Your first name"
              value={firstName}
            />

            <TextField
              autoCapitalize="words"
              editable={!isProviderNameLocked}
              label="Last name"
              onChangeText={setLastName}
              placeholder="Your last name"
              value={lastName}
            />

            {user?.role === "customer" ? (
              <>
                <TextField
                  keyboardType="phone-pad"
                  label="Phone"
                  onChangeText={setPhoneNumber}
                  placeholder="Phone number"
                  value={phoneNumber}
                />
                <TextField
                  label="Address"
                  onChangeText={setAddress}
                  placeholder="Address"
                  value={address}
                />

                <View style={styles.fieldBlock}>
                  <Text style={styles.label}>Service area</Text>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => setIsProvincePickerVisible(true)}
                    style={styles.provinceButton}
                  >
                    <Text style={styles.provinceText}>{serviceAreaLabel}</Text>
                    <ChevronDown color={colors.mutedText} size={20} />
                  </Pressable>
                </View>

                <TextField
                  label="Notes"
                  multiline
                  numberOfLines={4}
                  onChangeText={setNotes}
                  placeholder="Notes or preferences"
                  value={notes}
                />
              </>
            ) : null}

            {isProviderNameLocked ? (
              <Text style={styles.hintText}>
                Your legal name is locked while identity verification is under
                review or approved.
              </Text>
            ) : null}

            {message ? (
              <Text
                style={[
                  styles.messageText,
                  messageTone === "success"
                    ? styles.successMessageText
                    : styles.errorMessageText,
                ]}
              >
                {message}
              </Text>
            ) : null}

            <PrimaryButton
              disabled={
                isSaving ||
                isProviderNameLocked
              }
              label={isSaving ? "Saving..." : "Save"}
              onPress={() => void handleSave()}
            />
          </>
        )}
      </View>

      {user?.role === "customer" ? <LocationCascadePickerModal
        onClose={() => setIsProvincePickerVisible(false)}
        onSelect={(selection) => {
          setServiceProvince(selection.serviceProvince);
          setServiceLocationId(selection.serviceLocationId);
          setServiceAreaLabel(selection.label);
          setIsProvincePickerVisible(false);
        }}
        value={
          serviceLocationId
            ? ({
                serviceLocationId,
                serviceProvince,
                label: serviceAreaLabel,
              } satisfies ServiceAreaSelection)
            : null
        }
        visible={isProvincePickerVisible}
      /> : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: colors.surface,
    paddingTop: spacing.lg,
  },
  card: {
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  loadingBox: {
    minHeight: 260,
    alignItems: "center",
    justifyContent: "center",
  },
  fieldBlock: {
    gap: spacing.sm,
  },
  label: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  provinceButton: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
  },
  provinceText: {
    color: colors.text,
    fontSize: 16,
  },
  hintText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  messageText: {
    fontSize: 13,
  },
  successMessageText: {
    color: colors.primary,
  },
  errorMessageText: {
    color: colors.danger,
  },
});
