import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Image, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import {
  decideAdminIdentityVerification,
  decideAdminQualificationVerification,
  downloadVerificationFile,
  getAdminIdentityVerifications,
  getAdminQualificationVerifications,
} from "../../api/admin";
import { PrimaryButton } from "../../components/PrimaryButton";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import { getProviderTagLabel } from "../../constants/providerTags";
import { colors, radius, spacing } from "../../theme/theme";
import type {
  IdentityVerificationApplication,
  QualificationVerificationApplication,
  VerificationUploadFile,
} from "../../types/provider";
import { getErrorMessage } from "../../utils/errors";

type Selection =
  | { kind: "identity"; item: IdentityVerificationApplication }
  | { kind: "qualification"; item: QualificationVerificationApplication };

export function ProviderVerificationAdminPanel() {
  const [identities, setIdentities] = useState<IdentityVerificationApplication[]>([]);
  const [qualifications, setQualifications] = useState<QualificationVerificationApplication[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isActing, setIsActing] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setMessage("");
    try {
      const [nextIdentities, nextQualifications] = await Promise.all([
        getAdminIdentityVerifications(),
        getAdminQualificationVerifications(),
      ]);
      setIdentities(nextIdentities);
      setQualifications(nextQualifications);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  async function decide(status: "approved" | "rejected") {
    if (!selection) return;
    const note = rejectReason.trim();
    if (status === "rejected" && !note) {
      setMessage("Enter a rejection reason before rejecting the application.");
      return;
    }
    setIsActing(true);
    setMessage("");
    try {
      if (selection.kind === "identity") {
        await decideAdminIdentityVerification(selection.item.id, status, note);
      } else {
        await decideAdminQualificationVerification(selection.item.id, status, note);
      }
      Alert.alert(status === "approved" ? "Approved" : "Rejected", "The application has been reviewed.");
      setSelection(null);
      setRejectReason("");
      await load();
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  return <View style={styles.section}>
    <View style={styles.header}><View style={styles.flex}><Text style={styles.title}>Provider verification</Text><Text style={styles.subtitle}>Identity and service verification are reviewed separately.</Text></View><SecondaryButton label="Refresh" onPress={() => void load()} disabled={isLoading || isActing} /></View>
    {message ? <Text style={styles.error}>{message}</Text> : null}
    {isLoading ? <ActivityIndicator color={colors.primary} /> : <>
      <Queue title="Identity applications" empty="No identity applications pending review.">
        {identities.map((item) => <ReviewCard key={item.id} active={selection?.kind === "identity" && selection.item.id === item.id} title={`${item.submitted_first_name} ${item.submitted_last_name}`} subtitle={`Provider user #${item.user_id} · ${item.document_type.replace("_", " ")}`} onPress={() => { setSelection({ kind: "identity", item }); setRejectReason(""); }} />)}
      </Queue>
      <Queue title="Service verification applications" empty="No service verification applications pending review.">
        {qualifications.map((item) => <ReviewCard key={item.id} active={selection?.kind === "qualification" && selection.item.id === item.id} title={item.display_name} subtitle={`${item.entity_type} · ${item.service_categories.map(getProviderTagLabel).join(", ")}`} onPress={() => { setSelection({ kind: "qualification", item }); setRejectReason(""); }} />)}
      </Queue>
    </>}
    {selection ? <View style={styles.detail}>
      <View style={styles.header}><Text style={styles.detailTitle}>{selection.kind === "identity" ? "Identity review" : "Service verification review"}</Text><Pressable onPress={() => setSelection(null)}><Text style={styles.link}>Close</Text></Pressable></View>
      {selection.kind === "identity" ? <IdentityDetails item={selection.item} /> : <QualificationDetails item={selection.item} />}
      <TextField label="Rejection reason" multiline numberOfLines={3} onChangeText={setRejectReason} placeholder="Required only when rejecting" value={rejectReason} />
      <View style={styles.actions}><SecondaryButton disabled={isActing} label="Reject" onPress={() => void decide("rejected")} /><PrimaryButton disabled={isActing} isLoading={isActing} label="Approve" onPress={() => void decide("approved")} /></View>
    </View> : null}
  </View>;
}

function Queue({ title, empty, children }: { title: string; empty: string; children: React.ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return <View style={styles.queue}><Text style={styles.queueTitle}>{title}</Text>{hasChildren ? <View style={styles.list}>{children}</View> : <Text style={styles.empty}>{empty}</Text>}</View>;
}

function ReviewCard({ active, title, subtitle, onPress }: { active: boolean; title: string; subtitle: string; onPress: () => void }) {
  return <Pressable onPress={onPress} style={[styles.reviewCard, active ? styles.activeCard : null]}><View style={styles.header}><Text style={styles.cardTitle}>{title}</Text><Text style={styles.pending}>Pending</Text></View><Text style={styles.subtitle}>{subtitle}</Text></Pressable>;
}

function IdentityDetails({ item }: { item: IdentityVerificationApplication }) {
  return <View style={styles.rows}><Row label="Name" value={`${item.submitted_first_name} ${item.submitted_last_name}`} /><Row label="Date of birth" value={item.date_of_birth} /><Row label="Document type" value={item.document_type.replace("_", " ")} /><VerificationFiles files={item.document_files} /></View>;
}

function QualificationDetails({ item }: { item: QualificationVerificationApplication }) {
  return <View style={styles.rows}><Row label="Display name" value={item.display_name} /><Row label="Type" value={item.entity_type} />{item.legal_name ? <Row label="Legal name" value={item.legal_name} /> : null}{item.unique_enterprise_id ? <Row label="Enterprise ID" value={item.unique_enterprise_id} /> : null}<Row label="Description" value={item.description} /><Row label="Phone" value={item.contact_phone} /><Row label="Business address" value={item.business_address} /><Row label="Services" value={item.service_categories.map(getProviderTagLabel).join(", ")} /><Row label="Service areas" value={item.service_areas.map((area) => area.label ?? area.name).join(", ")} /><VerificationFiles files={item.qualification_files} /></View>;
}

function VerificationFiles({ files }: { files: VerificationUploadFile[] }) {
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [previewErrors, setPreviewErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (Platform.OS !== "web") return;
    let active = true;
    const createdUrls: string[] = [];
    setPreviewUrls({});
    setPreviewErrors({});

    void Promise.all(
      files.map(async (file) => {
        try {
          const blob = await downloadVerificationFile(file.file_url);
          const objectUrl = URL.createObjectURL(blob);
          createdUrls.push(objectUrl);
          if (active) {
            setPreviewUrls((current) => ({ ...current, [file.file_url]: objectUrl }));
          } else {
            URL.revokeObjectURL(objectUrl);
          }
        } catch (error) {
          if (active) {
            setPreviewErrors((current) => ({
              ...current,
              [file.file_url]: getErrorMessage(error),
            }));
          }
        }
      }),
    );

    return () => {
      active = false;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  function openFile(file: VerificationUploadFile) {
    if (Platform.OS !== "web") {
      Alert.alert("File preview", "Images are shown below. Open PDF verification files from the web admin dashboard.");
      return;
    }
    const objectUrl = previewUrls[file.file_url];
    if (!objectUrl) {
      Alert.alert(
        "File not ready",
        previewErrors[file.file_url] || "The protected file is still loading. Try again shortly.",
      );
      return;
    }
    window.open(objectUrl, "_blank", "noopener,noreferrer");
  }
  return <View style={styles.files}><Text style={styles.rowLabel}>Files</Text>{files.map((file) => {
    const previewUrl = previewUrls[file.file_url];
    const previewError = previewErrors[file.file_url];
    return <Pressable key={`${file.file_url}-${file.original_file_name}`} onPress={() => openFile(file)} style={styles.fileCard}>{file.content_type.startsWith("image/") && previewUrl ? <Image resizeMode="contain" source={{ uri: previewUrl }} style={styles.preview} /> : file.content_type.startsWith("image/") && !previewError ? <ActivityIndicator color={colors.primary} style={styles.preview} /> : null}<Text style={styles.link}>{file.original_file_name}</Text><Text style={previewError ? styles.error : styles.subtitle}>{previewError || `${file.content_type} · tap to open`}</Text></Pressable>;
  })}</View>;
}

function Row({ label, value }: { label: string; value: string }) { return <View style={styles.row}><Text style={styles.rowLabel}>{label}</Text><Text style={styles.rowValue}>{value || "-"}</Text></View>; }

const styles = StyleSheet.create({
  section: { gap: spacing.md }, header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md }, flex: { flex: 1 }, title: { color: colors.text, fontSize: 20, fontWeight: "700" }, subtitle: { color: colors.mutedText, fontSize: 13, marginTop: spacing.xs }, error: { color: colors.danger }, queue: { gap: spacing.sm }, queueTitle: { color: colors.text, fontSize: 16, fontWeight: "700" }, list: { gap: spacing.sm }, empty: { color: colors.mutedText, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md },
  reviewCard: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.background, padding: spacing.md, gap: spacing.xs }, activeCard: { borderColor: colors.primary }, cardTitle: { flex: 1, color: colors.text, fontWeight: "700" }, pending: { color: "#8A5A00", fontSize: 12, fontWeight: "700" }, detail: { borderWidth: 1, borderColor: colors.primary, borderRadius: radius.md, backgroundColor: colors.background, padding: spacing.lg, gap: spacing.md }, detailTitle: { color: colors.text, fontSize: 18, fontWeight: "700" }, link: { color: colors.primary, fontWeight: "700" }, rows: { gap: spacing.sm }, row: { flexDirection: "row", gap: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border, paddingBottom: spacing.sm }, rowLabel: { width: 120, color: colors.mutedText }, rowValue: { flex: 1, color: colors.text }, actions: { gap: spacing.sm }, files: { gap: spacing.sm }, fileCard: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.sm, gap: spacing.xs }, preview: { width: "100%", height: 220, backgroundColor: colors.surface, borderRadius: radius.sm },
});
