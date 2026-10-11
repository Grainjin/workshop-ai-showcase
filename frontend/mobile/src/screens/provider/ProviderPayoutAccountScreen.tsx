import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import {
  createProviderSubmerchant,
  getProviderSubmerchant,
  updateProviderSubmerchant,
} from "../../api/marketplace";
import { PrimaryButton } from "../../components/PrimaryButton";
import { ScreenContainer } from "../../components/ScreenContainer";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import { colors, radius, spacing } from "../../theme/theme";
import { useAuth } from "../../context/AuthContext";
import { useProviderPayoutStatus } from "../../context/ProviderPayoutStatusContext";
import { useProviderProfileGate } from "../../context/ProviderProfileGateContext";
import type {
  ProviderSubmerchant,
  ProviderSubmerchantPayload,
  SubmerchantType,
} from "../../types/marketplace";
import { getErrorMessage } from "../../utils/errors";
import { isValidTurkishIban } from "../../utils/iban";

type FormState = {
  submerchant_type: SubmerchantType;
  name: string;
  email: string;
  gsm_number: string;
  address: string;
  iban: string;
  contact_name: string;
  contact_surname: string;
  identity_number: string;
  tax_office: string;
  tax_number: string;
  legal_company_title: string;
};

type FieldErrors = Partial<Record<keyof FormState, string>>;

const TYPE_OPTIONS: Array<{ label: string; value: SubmerchantType }> = [
  { label: "Personal", value: "PERSONAL" },
  { label: "Private company", value: "PRIVATE_COMPANY" },
  { label: "Limited / joint stock", value: "LIMITED_OR_JOINT_STOCK_COMPANY" },
];

const EMPTY_FORM: FormState = {
  submerchant_type: "PERSONAL",
  name: "",
  email: "",
  gsm_number: "",
  address: "",
  iban: "",
  contact_name: "",
  contact_surname: "",
  identity_number: "",
  tax_office: "",
  tax_number: "",
  legal_company_title: "",
};

export function ProviderPayoutAccountScreen() {
  const { user } = useAuth();
  const { refresh: refreshPayoutStatus } = useProviderPayoutStatus();
  const { refreshProviderProfileStatus } = useProviderProfileGate();
  const [submerchant, setSubmerchant] = useState<ProviderSubmerchant | null>(null);
  const [form, setForm] = useState<FormState>({
    ...EMPTY_FORM,
    name: user?.name ?? "",
    email: user?.email ?? "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const load = useCallback(async () => {
    setIsLoading(true);
    setMessage("");
    try {
      const result = await getProviderSubmerchant();
      setSubmerchant(result);
      if (result) {
        setForm(toFormState(result));
      }
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => {
      if (!current[field]) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      return next;
    });
    setMessage("");
    setSaveMessage("");
  }

  async function save() {
    const validationErrors = validateForm(form);
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setMessage("");
      setSaveMessage("");
      return;
    }

    setIsSaving(true);
    setFieldErrors({});
    setMessage("");
    setSaveMessage("");
    try {
      const payload = toPayload(form);
      const result = submerchant
        ? await updateProviderSubmerchant(payload)
        : await createProviderSubmerchant(payload);
      setSubmerchant(result);
      setForm(toFormState(result));
      await Promise.all([
        refreshPayoutStatus(),
        refreshProviderProfileStatus(),
      ]);
      if (result.status === "rejected" || result.status === "update_failed") {
        setMessage(
          result.iyzico_error_message ||
            "The payout account was rejected. Review the details and try again.",
        );
      }
      setSaveMessage(
        result.status === "rejected" || result.status === "update_failed"
          ? "Payout account was not accepted."
          : result.status === "active"
          ? "Payout account is active."
          : "Payout account details saved. Check the status below.",
      );
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  const isLimitedCompany =
    form.submerchant_type === "LIMITED_OR_JOINT_STOCK_COMPANY";

  return (
    <ScreenContainer contentStyle={styles.content}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.title}>Payout account</Text>
          <Text style={styles.subtitle}>
            Add your payout details. We validate them locally and synchronize with iyzico Sandbox.
          </Text>
        </View>
        <SecondaryButton
          disabled={isLoading || isSaving}
          label="Refresh"
          onPress={() => void load()}
        />
      </View>

      {isLoading ? (
        <ActivityIndicator accessibilityLabel="Loading payout account" color={colors.primary} />
      ) : (
        <>
          {message ? (
            <Text accessibilityRole="alert" style={styles.error}>
              {message}
            </Text>
          ) : null}
          <StatusCard submerchant={submerchant} />
          {saveMessage ? (
            <Text style={submerchant?.status === "active" ? styles.success : styles.error}>
              {saveMessage}
            </Text>
          ) : null}

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Business type</Text>
            <View style={styles.typeRow}>
              {TYPE_OPTIONS.map((option) => {
                const selected = form.submerchant_type === option.value;
                return (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    key={option.value}
                    onPress={() => updateField("submerchant_type", option.value)}
                    style={[styles.typeOption, selected ? styles.typeOptionSelected : null]}
                  >
                    <Text style={[styles.typeLabel, selected ? styles.typeLabelSelected : null]}>
                      {option.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Payout details</Text>
            <TextField error={fieldErrors.name} label="Name or legal company title" value={form.name} onChangeText={(value) => updateField("name", value)} />
            <TextField error={fieldErrors.email} label="Email" keyboardType="email-address" value={form.email} onChangeText={(value) => updateField("email", value)} />
            <TextField error={fieldErrors.gsm_number} label="Phone number" keyboardType="phone-pad" value={form.gsm_number} onChangeText={(value) => updateField("gsm_number", value)} />
            <TextField error={fieldErrors.iban} label="IBAN" autoCapitalize="characters" value={form.iban} onChangeText={(value) => updateField("iban", value)} />
            <TextField error={fieldErrors.address} label="Address" multiline numberOfLines={3} value={form.address} onChangeText={(value) => updateField("address", value)} />
          </View>

          {form.submerchant_type === "PERSONAL" ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Personal identity</Text>
              <TextField error={fieldErrors.contact_name} label="First name" value={form.contact_name} onChangeText={(value) => updateField("contact_name", value)} />
              <TextField error={fieldErrors.contact_surname} label="Last name" value={form.contact_surname} onChangeText={(value) => updateField("contact_surname", value)} />
              <TextField error={fieldErrors.identity_number} label="Identity number" value={form.identity_number} onChangeText={(value) => updateField("identity_number", value)} />
            </View>
          ) : (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Company information</Text>
              <TextField error={fieldErrors.tax_office} label="Tax office" value={form.tax_office} onChangeText={(value) => updateField("tax_office", value)} />
              <TextField error={fieldErrors.legal_company_title} label="Legal company title" value={form.legal_company_title} onChangeText={(value) => updateField("legal_company_title", value)} />
              {isLimitedCompany ? (
                <TextField error={fieldErrors.tax_number} label="Tax number" value={form.tax_number} onChangeText={(value) => updateField("tax_number", value)} />
              ) : null}
            </View>
          )}

          <PrimaryButton
            disabled={isSaving}
            isLoading={isSaving}
            label="Save payout details"
            onPress={() => void save()}
          />
        </>
      )}
    </ScreenContainer>
  );
}

function StatusCard({ submerchant }: { submerchant: ProviderSubmerchant | null }) {
  const status = submerchant?.status ?? "draft";
  const isValid = status === "active";
  const isError = !isValid;
  const label = getSubmerchantStatusLabel(status);

  return (
    <View style={[styles.statusCard, isError ? styles.statusCardError : null]}>
      <View style={styles.statusTopLine}>
        <View>
        <Text style={styles.statusEyebrow}>Sandbox synchronization</Text>
          <Text
            style={[
              styles.statusTitle,
              isValid ? styles.statusTitleValid : styles.statusTitleError,
            ]}
          >
            {label}
          </Text>
        </View>
        <Text style={styles.statusBadge}>Payout details</Text>
      </View>
      <Text style={styles.statusBody}>
        {submerchant
          ? isError
            ? "Update the details below and save them again."
            : status === "active"
              ? "The payout details were accepted by iyzico Sandbox."
              : "Complete the details below to submit this payout account."
          : "No payout account has been submitted yet."}
      </Text>
    </View>
  );
}

function getSubmerchantStatusLabel(status: string) {
  return {
    draft: "Details incomplete",
    active: "Details valid",
    rejected: "Needs correction",
    update_failed: "Needs correction",
  }[status] ?? status;
}

function toFormState(submerchant: ProviderSubmerchant): FormState {
  return {
    submerchant_type: submerchant.submerchant_type,
    name: submerchant.name || "",
    email: submerchant.email || "",
    gsm_number: submerchant.gsm_number || "",
    address: submerchant.address || "",
    iban: submerchant.iban || "",
    contact_name: submerchant.contact_name || "",
    contact_surname: submerchant.contact_surname || "",
    identity_number: submerchant.identity_number || "",
    tax_office: submerchant.tax_office || "",
    tax_number: submerchant.tax_number || "",
    legal_company_title: submerchant.legal_company_title || "",
  };
}

function toPayload(form: FormState): ProviderSubmerchantPayload {
  return {
    ...form,
    name: form.name.trim(),
    email: form.email.trim(),
    gsm_number: form.gsm_number.trim(),
    address: form.address.trim(),
    iban: form.iban.trim(),
    contact_name: nullable(form.contact_name),
    contact_surname: nullable(form.contact_surname),
    identity_number: nullable(form.identity_number),
    tax_office: nullable(form.tax_office),
    tax_number: nullable(form.tax_number),
    legal_company_title: nullable(form.legal_company_title),
    currency: "TRY",
  };
}

function nullable(value: string) {
  const cleanValue = value.trim();
  return cleanValue || null;
}

function validateForm(form: FormState) {
  const errors: FieldErrors = {};
  const requiredFields: Array<[keyof FormState, string]> = [
    ["name", "Name"],
    ["email", "Email"],
    ["gsm_number", "Phone number"],
    ["iban", "IBAN"],
    ["address", "Address"],
  ];
  if (form.submerchant_type === "PERSONAL") {
    requiredFields.push(
      ["contact_name", "First name"],
      ["contact_surname", "Last name"],
      ["identity_number", "Identity number"],
    );
  } else {
    requiredFields.push(
      ["tax_office", "Tax office"],
      ["legal_company_title", "Legal company title"],
    );
    if (form.submerchant_type === "LIMITED_OR_JOINT_STOCK_COMPANY") {
      requiredFields.push(["tax_number", "Tax number"]);
    }
  }

  for (const [field, label] of requiredFields) {
    if (!form[field].trim()) {
      errors[field] = `${label} is required.`;
    }
  }

  if (!errors.email && !/^\S+@\S+\.\S+$/.test(form.email.trim())) {
    errors.email = "Enter a valid email address.";
  }

  const normalizedIban = form.iban.replace(/\s/g, "").toUpperCase();
  if (!errors.iban && !isValidTurkishIban(normalizedIban)) {
    errors.iban = "Enter a valid Turkish IBAN.";
  }

  return errors;
}

const styles = StyleSheet.create({
  content: { gap: spacing.lg },
  header: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  headerCopy: { flex: 1, gap: spacing.xs },
  title: { color: colors.text, fontSize: 28, fontWeight: "800" },
  subtitle: { color: colors.mutedText, fontSize: 14, lineHeight: 21 },
  section: { gap: spacing.md, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.background, padding: spacing.lg },
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: "800" },
  typeRow: { gap: spacing.sm },
  typeOption: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, backgroundColor: colors.background },
  typeOptionSelected: { borderColor: colors.primary, backgroundColor: "#E9F7F3" },
  typeLabel: { color: colors.text, fontSize: 15, fontWeight: "600" },
  typeLabelSelected: { color: colors.primary, fontWeight: "800" },
  hint: { color: colors.mutedText, fontSize: 13 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 20 },
  success: { color: colors.primary, fontSize: 14, lineHeight: 20 },
  statusCard: { gap: spacing.sm, borderWidth: 1, borderColor: "#B8E7D8", borderRadius: radius.md, backgroundColor: "#F0FBF7", padding: spacing.lg },
  statusCardError: { borderColor: "#F1B9B4", backgroundColor: "#FFF7F6" },
  statusTopLine: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  statusEyebrow: { color: colors.mutedText, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.8 },
  statusTitle: { fontSize: 22, fontWeight: "800", marginTop: spacing.xs },
  statusTitleValid: { color: colors.primary },
  statusTitleError: { color: colors.danger },
  statusBadge: { color: colors.mutedText, fontSize: 12, fontWeight: "700", textTransform: "uppercase" },
  statusBody: { color: colors.text, fontSize: 14, lineHeight: 21 },
  statusCode: { color: colors.mutedText, fontSize: 13 },
});
