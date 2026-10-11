import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import * as DocumentPicker from "expo-document-picker";
import { Check, ChevronRight, FileText, MapPin, Trash2 } from "lucide-react-native";
import { useCallback, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getIdentityVerification,
  getProviderProfile,
  getProviderServiceAreas,
  getProviderVerificationStatus,
  getQualificationVerification,
  type LocalVerificationFile,
  submitIdentityVerification,
  submitQualificationVerification,
  uploadQualificationFiles,
} from "../../api/provider";
import {
  getPublicProviderPortfolios,
  getPublicProviderReviews,
} from "../../api/customer";
import { getProviderSubmerchant } from "../../api/marketplace";
import { DateTimeField } from "../../components/DateTimeField";
import { LocationCascadePickerModal } from "../../components/LocationCascadePickerModal";
import { LocationPickerModal } from "../../components/LocationPickerModal";
import { PortfolioCard } from "../../components/PortfolioCard";
import { PrimaryButton } from "../../components/PrimaryButton";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import { getProviderTagLabel, PROVIDER_TAGS } from "../../constants/providerTags";
import { useAuth } from "../../context/AuthContext";
import { useProviderProfileGate } from "../../context/ProviderProfileGateContext";
import type { RootStackParamList } from "../../navigation/types";
import { colors, radius, spacing } from "../../theme/theme";
import type { PaginatedData } from "../../types/chat";
import type { SelectedLocation, ServiceAreaSelection } from "../../types/location";
import type {
  IdentityVerificationApplication,
  ProviderPortfolio,
  ProviderProfile,
  ProviderServiceArea,
  ProviderVerificationStatus,
  QualificationVerificationApplication,
  VerificationStatus,
} from "../../types/provider";
import type { ProviderSubmerchant } from "../../types/marketplace";
import type { Review } from "../../types/review";
import { getErrorMessage } from "../../utils/errors";

const MAX_FILES = 5;
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const ACCEPTED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const REVIEW_PAGE_SIZE = 10;

export function ProviderHomeScreen() {
  const { isProviderProfileLoading, isProviderProfileRequired } =
    useProviderProfileGate();

  if (isProviderProfileLoading) {
    return <ActivityIndicator color={colors.primary} style={styles.loader} />;
  }

  if (isProviderProfileRequired) {
    return <ProviderVerificationScreen />;
  }

  return <ProviderHomeContent />;
}

export function ProviderVerificationScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { refreshProviderProfileStatus } = useProviderProfileGate();
  const [status, setStatus] = useState<ProviderVerificationStatus | null>(null);
  const [payoutAccount, setPayoutAccount] = useState<ProviderSubmerchant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setMessage("");
    try {
      const nextStatus = await getProviderVerificationStatus();
      setStatus(nextStatus);
      setPayoutAccount(await getProviderSubmerchant());
      await refreshProviderProfileStatus();
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [refreshProviderProfileStatus]);

  useFocusEffect(useCallback(() => void load(), [load]));

  if (isLoading) return <ActivityIndicator color={colors.primary} style={styles.loader} />;

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.header}>
        <View style={styles.flex}>
          <Text style={styles.title}>Provider verification</Text>
          <Text style={styles.subtitle}>Complete the three independent steps before accepting new orders.</Text>
        </View>
        <SecondaryButton label="Refresh" onPress={() => void load()} />
      </View>
      <ProgressCard status={status} payoutStatus={payoutAccount?.status ?? "draft"} />
      {message ? <Text style={styles.error}>{message}</Text> : null}
      <VerificationEntryCard
        label="1. ID verification"
        status={status?.identity_status ?? "not_submitted"}
        description="Submit your identity details and supporting document."
        onPress={() => navigation.navigate("ProviderIdentityVerification")}
      />
      <VerificationEntryCard
        label="2. Service verification"
        status={status?.qualification_status ?? "not_submitted"}
        description="Submit your service details, areas, and supporting files."
        onPress={() => navigation.navigate("ProviderServiceVerification")}
      />
      <PayoutAccountStep
        navigation={navigation}
        status={payoutAccount?.status ?? "draft"}
      />
    </ScrollView>
  );
}

export function ProviderIdentityVerificationScreen() {
  const { user } = useAuth();
  const [status, setStatus] = useState<ProviderVerificationStatus | null>(null);
  const [application, setApplication] = useState<IdentityVerificationApplication | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const nextStatus = await getProviderVerificationStatus();
      setStatus(nextStatus);
      setApplication(nextStatus?.identity_application_id ? await getIdentityVerification() : null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => void load(), [load]));

  if (isLoading) return <ActivityIndicator color={colors.primary} style={styles.loader} />;
  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.headerContent}>
        <Text style={styles.title}>ID verification</Text>
        <Text style={styles.subtitle}>Update your identity details and submit them for review.</Text>
        <IdentityStep
          application={application}
          firstName={user?.first_name || ""}
          lastName={user?.last_name || ""}
          onSubmitted={() => void load()}
          status={status?.identity_status ?? "not_submitted"}
        />
      </View>
    </ScrollView>
  );
}

export function ProviderServiceVerificationScreen() {
  const { refreshProviderProfileStatus } = useProviderProfileGate();
  const [status, setStatus] = useState<ProviderVerificationStatus | null>(null);
  const [application, setApplication] = useState<QualificationVerificationApplication | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const nextStatus = await getProviderVerificationStatus();
      setStatus(nextStatus);
      setApplication(nextStatus?.qualification_application_id ? await getQualificationVerification() : null);
      await refreshProviderProfileStatus();
    } finally {
      setIsLoading(false);
    }
  }, [refreshProviderProfileStatus]);

  useFocusEffect(useCallback(() => void load(), [load]));

  if (isLoading) return <ActivityIndicator color={colors.primary} style={styles.loader} />;
  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.headerContent}>
        <Text style={styles.title}>Service verification</Text>
        <Text style={styles.subtitle}>Update your service details and submit them for review.</Text>
        <QualificationStep
          application={application}
          onSubmitted={() => void load()}
          status={status?.qualification_status ?? "not_submitted"}
        />
      </View>
    </ScrollView>
  );
}

function ProviderHomeContent() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [profile, setProfile] = useState<ProviderProfile | null>(null);
  const [serviceAreas, setServiceAreas] = useState<ProviderServiceArea[]>([]);
  const [portfolios, setPortfolios] = useState<ProviderPortfolio[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewPage, setReviewPage] = useState(1);
  const [reviewPaging, setReviewPaging] = useState<PaginatedData<Review> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [nextProfile, serviceAreaResult] = await Promise.all([
        getProviderProfile(),
        getProviderServiceAreas(),
      ]);
      if (!nextProfile) throw new Error("Provider profile could not be loaded.");
      const [nextPortfolios, nextReviews] = await Promise.all([
        getPublicProviderPortfolios(nextProfile.id, 1, 4),
        getPublicProviderReviews(nextProfile.id, 1, REVIEW_PAGE_SIZE),
      ]);
      setProfile(nextProfile);
      setServiceAreas(serviceAreaResult?.service_areas ?? []);
      setPortfolios(nextPortfolios?.items ?? []);
      setReviews(nextReviews?.items ?? []);
      setReviewPaging(nextReviews ?? null);
      setReviewPage(1);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => void load(), [load]));

  async function loadMoreReviews() {
    if (isLoadingMore || !reviewPaging?.has_next) return;

    setIsLoadingMore(true);
    try {
      const nextPage = reviewPage + 1;
      if (!profile) return;
      const nextData = await getPublicProviderReviews(profile.id, nextPage, REVIEW_PAGE_SIZE);
      if (nextData) {
        setReviews((current) => [...current, ...nextData.items]);
        setReviewPaging(nextData);
        setReviewPage(nextPage);
      }
    } finally {
      setIsLoadingMore(false);
    }
  }

  return (
    <FlatList
      ListEmptyComponent={
        isLoading ? null : <Text style={styles.emptyText}>{error || "No reviews yet"}</Text>
      }
      ListFooterComponent={
        isLoadingMore ? <ActivityIndicator color={colors.primary} style={styles.footerLoader} /> : null
      }
      ListHeaderComponent={
        <View style={styles.headerContent}>
          <View style={styles.profileSummaryCard}>
            <View style={styles.profileSummaryMain}>
              <View style={styles.businessTitleRow}>
                <Text numberOfLines={1} style={styles.businessName}>
                  {profile?.business_name ?? "Provider"}
                </Text>
                <Text style={styles.serviceVerifiedBadge}>Service verified</Text>
              </View>
              <View style={styles.statusRow}>
                <OpenStatusBadge isOpen={Boolean(profile?.is_open)} />
                <OnlineStatusBadge isOnline={Boolean(profile?.is_online)} />
              </View>
              <Text style={styles.bioText}>{profile?.bio || "No business description yet."}</Text>
              <Text style={styles.metaText}>
                Business address: {profile?.address || "Not set"}
              </Text>
              <Text style={styles.metaText}>
                Service areas: {formatServiceAreas(serviceAreas)}
              </Text>
              <Text style={styles.metaText}>
                {formatRating(profile)} · {profile?.hourly_rate ?? "-"} / hr
              </Text>
              <View style={styles.tagWrap}>
                {(profile?.tags ?? []).map((tag) => (
                  <View key={tag} style={styles.serviceTag}>
                    <Text style={styles.serviceTagText}>{getProviderTagLabel(tag)}</Text>
                  </View>
                ))}
              </View>
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("ProviderOperatingSettings")}
              style={styles.settingsButton}
            >
              <Text style={styles.settingsButtonText}>Operating settings</Text>
            </Pressable>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Portfolios</Text>
            <Pressable accessibilityRole="button" onPress={() => navigation.navigate("ProviderPortfolioList")} style={styles.moreButton}>
              <Text style={styles.moreText}>Manage portfolios</Text>
              <ChevronRight color={colors.primary} size={18} />
            </Pressable>
          </View>

          {isLoading ? (
            <ActivityIndicator color={colors.primary} />
          ) : portfolios.length > 0 ? (
            <FlatList
              ItemSeparatorComponent={() => <View style={styles.portfolioGap} />}
              data={portfolios}
              horizontal
              keyExtractor={(item) => String(item.id)}
              renderItem={({ item }) => (
                <PortfolioCard compact onPress={() => navigation.navigate("ProviderPortfolioDetail", { portfolioId: item.id })} portfolio={item} />
              )}
              showsHorizontalScrollIndicator={false}
            />
          ) : (
            <Text style={styles.emptyText}>No portfolios uploaded yet</Text>
          )}

          <Text style={styles.sectionTitle}>Reviews</Text>
        </View>
      }
      contentContainerStyle={styles.approvedContent}
      data={reviews}
      keyExtractor={(item) => String(item.id)}
      onEndReached={() => void loadMoreReviews()}
      onEndReachedThreshold={0.4}
      renderItem={({ item }) => <ReviewRow review={item} />}
      style={styles.container}
    />
  );
}

function OpenStatusBadge({ isOpen }: { isOpen: boolean }) {
  return (
    <View style={styles.statusBadge}>
      <View style={[styles.statusDot, isOpen ? styles.statusDotActive : styles.statusDotInactive]} />
      <Text style={styles.statusBadgeText}>{isOpen ? "Open" : "Closed"}</Text>
    </View>
  );
}

function OnlineStatusBadge({ isOnline }: { isOnline: boolean }) {
  return (
    <View style={styles.statusBadge}>
      <View style={[styles.statusDot, isOnline ? styles.statusDotActive : styles.statusDotInactive]} />
      <Text style={styles.statusBadgeText}>{isOnline ? "Online" : "Offline"}</Text>
    </View>
  );
}

function formatServiceAreas(areas: ProviderServiceArea[]) {
  return areas.length > 0 ? areas.map((area) => area.label || area.name).join(", ") : "Not set";
}

function formatRating(profile: ProviderProfile | null) {
  if (profile?.average_rating == null || !profile.review_count) return "No rating yet";
  return `${profile.average_rating.toFixed(1)} stars · ${profile.review_count} reviews`;
}

function ReviewRow({ review }: { review: Review }) {
  return (
    <View style={styles.reviewCard}>
      <View style={styles.reviewTopRow}>
        <Text style={styles.ratingText}>{review.rating.toFixed(1)} stars</Text>
        <Text style={styles.reviewDate}>{formatReviewDate(review.created_at)}</Text>
      </View>
      <Text style={styles.reviewComment}>{review.comment || "No comment provided."}</Text>
    </View>
  );
}

function formatReviewDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function ProgressCard({
  status,
  payoutStatus,
}: {
  status: ProviderVerificationStatus | null;
  payoutStatus: string;
}) {
  const steps = [
    {
      label: "1. ID verification",
      value: status?.identity_status ?? "not_submitted",
      complete: status?.identity_status === "approved",
    },
    {
      label: "2. Service verification",
      value: status?.qualification_status ?? "not_submitted",
      complete: status?.qualification_status === "approved",
    },
    {
      label: "3. Payout account",
      value: payoutStatus,
      complete: payoutStatus === "active",
    },
  ];
  return (
    <View style={styles.stepper}>
      {steps.map(({ label, value, complete }, index) => (
        <View key={label} style={styles.stepItem}>
          <View style={[styles.stepDot, complete ? styles.stepDotApproved : null]}>
            <Text style={[styles.stepNumber, complete ? styles.stepNumberApproved : null]}>
              {complete ? "✓" : index + 1}
            </Text>
          </View>
          <View style={styles.stepCopy}>
            <Text style={styles.progressLabel}>{label}</Text>
            {index < 2 ? <StatusBadge status={value as VerificationStatus} /> : <PayoutStatusBadge status={value} />}
          </View>
          {index < steps.length - 1 ? <View style={styles.stepConnector} /> : null}
        </View>
      ))}
    </View>
  );
}

function PayoutAccountStep({
  navigation,
  status,
}: {
  navigation: NativeStackNavigationProp<RootStackParamList>;
  status: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Open payout account"
      onPress={() => navigation.navigate("ProviderPayoutAccount")}
      style={styles.card}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>3. Payout account</Text>
        <PayoutStatusBadge status={status} />
      </View>
      <Text style={styles.hint}>
        Add and synchronize the account that receives marketplace payouts.
      </Text>
      <View style={styles.sectionHeader}>
        <Text style={styles.link}>{status === "active" ? "Review payout details" : "Complete payout details"}</Text>
        <ChevronRight color={colors.primary} size={20} />
      </View>
    </Pressable>
  );
}

function VerificationEntryCard({
  label,
  status,
  description,
  onPress,
}: {
  label: string;
  status: VerificationStatus;
  description: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Open ${label}`}
      onPress={onPress}
      style={styles.card}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{label}</Text>
        <StatusBadge status={status} />
      </View>
      <Text style={styles.hint}>{description}</Text>
      <View style={styles.sectionHeader}>
        <Text style={styles.link}>{status === "approved" ? "Review submission" : "Open details"}</Text>
        <ChevronRight color={colors.primary} size={20} />
      </View>
    </Pressable>
  );
}

function IdentityStep({ application, firstName, lastName, onSubmitted, status }: {
  application: IdentityVerificationApplication | null; firstName: string; lastName: string; onSubmitted: () => void; status: VerificationStatus;
}) {
  const [dateOfBirth, setDateOfBirth] = useState(application?.date_of_birth ?? "");
  const [documentType, setDocumentType] = useState<"national_id" | "passport">(application?.document_type ?? "national_id");
  const [files, setFiles] = useState<LocalVerificationFile[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const canSubmit = status === "not_submitted" || status === "rejected";

  async function submit() {
    if (!firstName.trim() || !lastName.trim()) {
      setError("Add your first and last name in Account → Edit profile before submitting.");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateOfBirth) || files.length === 0) {
      setError("Enter date of birth as YYYY-MM-DD and attach at least one file."); return;
    }
    setIsSubmitting(true); setError("");
    try {
      await submitIdentityVerification({ dateOfBirth, documentType, files });
      Alert.alert("Submitted", "Your identity application is now under review."); onSubmitted();
    } catch (submitError) { setError(getErrorMessage(submitError)); }
    finally { setIsSubmitting(false); }
  }

  return <View style={styles.card}>
    <View style={styles.cardHeader}><Text style={styles.cardTitle}>1. Identity verification</Text><StatusBadge status={status} /></View>
    {!canSubmit ? <ApplicationSummary rows={[
      ["Name", `${application?.submitted_first_name ?? firstName} ${application?.submitted_last_name ?? lastName}`],
      ["Date of birth", application?.date_of_birth ?? "-"], ["Document", documentLabel(application?.document_type)],
      ["Files", String(application?.document_files.length ?? 0)],
    ]} note="The application cannot be changed or cancelled while pending. Approved identity details stay locked." /> :
      <View style={styles.form}>
        <ReadOnlyRow label="First name" value={firstName} /><ReadOnlyRow label="Last name" value={lastName} />
        <Text style={styles.hint}>These names are read from your account.</Text>
        {!firstName.trim() || !lastName.trim() ? <Text style={styles.error}>Complete both names in Account → Edit profile first.</Text> : null}
        <DateTimeField
          label="Date of birth"
          maximumDate={new Date()}
          mode="date"
          onChange={setDateOfBirth}
          value={dateOfBirth}
        />
        <ChoiceRow options={[["national_id", "National ID"], ["passport", "Passport"]]} selected={documentType} onSelect={(value) => setDocumentType(value as "national_id" | "passport")} />
        <FilePicker files={files} onChange={setFiles} />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <PrimaryButton disabled={!firstName.trim() || !lastName.trim()} isLoading={isSubmitting} label="Submit identity verification" onPress={() => void submit()} />
      </View>}
  </View>;
}

function QualificationStep({ application, onSubmitted, status }: { application: QualificationVerificationApplication | null; onSubmitted: () => void; status: VerificationStatus }) {
  const [entityType, setEntityType] = useState<"personal" | "organisation">(application?.entity_type ?? "personal");
  const [legalName, setLegalName] = useState(application?.legal_name ?? "");
  const [enterpriseId, setEnterpriseId] = useState(application?.unique_enterprise_id ?? "");
  const [description, setDescription] = useState(application?.description ?? "");
  const [phone, setPhone] = useState(application?.contact_phone ?? "");
  const [address, setAddress] = useState<SelectedLocation | null>(application ? {
    label: application.business_address,
    latitude: application.business_latitude,
    longitude: application.business_longitude,
    placeId: application.business_place_id,
  } : null);
  const [categories, setCategories] = useState<string[]>(application?.service_categories ?? []);
  const [areas, setAreas] = useState<ProviderServiceArea[]>(application?.service_areas ?? []);
  const [files, setFiles] = useState<LocalVerificationFile[]>([]);
  const [showAddressPicker, setShowAddressPicker] = useState(false);
  const [showAreaPicker, setShowAreaPicker] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const canSubmit = status === "not_submitted" || status === "rejected";

  async function submit() {
    if (!description.trim() || !phone.trim() || !address || categories.length === 0 || areas.length === 0 || files.length === 0 || (entityType === "organisation" && (!legalName.trim() || !enterpriseId.trim()))) {
      setError("Complete every required field and attach at least one file."); return;
    }
    setIsSubmitting(true); setError("");
    try {
      const uploaded = await uploadQualificationFiles(files);
      if (!uploaded) throw new Error("The qualification files could not be uploaded.");
      await submitQualificationVerification({
        entity_type: entityType,
        legal_name: entityType === "organisation" ? legalName.trim() : null,
        unique_enterprise_id: entityType === "organisation" ? enterpriseId.trim() : null,
        description: description.trim(), contact_phone: phone.trim(), business_address: address.label,
        business_place_id: address.placeId, business_latitude: address.latitude, business_longitude: address.longitude,
        service_categories: categories, service_location_ids: areas.map((area) => area.id), qualification_files: uploaded.files,
      });
      Alert.alert("Submitted", "Your service verification application is now under review."); onSubmitted();
    } catch (submitError) { setError(getErrorMessage(submitError)); }
    finally { setIsSubmitting(false); }
  }

  function addArea(selection: ServiceAreaSelection) {
    if (!areas.some((area) => area.id === selection.serviceLocationId)) {
      const depth = selection.label.split(" / ").length;
      setAreas((current) => [...current, {
        id: selection.serviceLocationId,
        name: selection.label,
        label: selection.label,
        serviceProvince: selection.serviceProvince,
        level: depth === 1 ? "province" : depth === 2 ? "city" : "district",
      }]);
    }
    setShowAreaPicker(false);
  }

  return <View style={styles.card}>
    <View style={styles.cardHeader}><Text style={styles.cardTitle}>2. Service verification</Text><StatusBadge status={status} /></View>
    {!canSubmit ? <ApplicationSummary rows={[
      ["Provider type", application?.entity_type ?? "-"], ["Display name", application?.display_name ?? "-"],
      ["Business address", application?.business_address ?? "-"], ["Services", application?.service_categories.map(getProviderTagLabel).join(", ") ?? "-"],
      ["Service areas", application?.service_areas.map((area) => area.label ?? area.name).join(", ") ?? "-"],
      ["Files", String(application?.qualification_files.length ?? 0)],
    ]} note="The application cannot be changed or cancelled while pending." /> :
      <View style={styles.form}>
        <Text style={styles.fieldLabel}>Provider type</Text>
        <ChoiceRow options={[["personal", "Personal"], ["organisation", "Organisation"]]} selected={entityType} onSelect={(value) => setEntityType(value as "personal" | "organisation")} />
        {entityType === "organisation" ? <><TextField label="Legal organisation name" onChangeText={setLegalName} value={legalName} /><TextField label="Unique enterprise ID" onChangeText={setEnterpriseId} value={enterpriseId} /></> : <Text style={styles.hint}>Your approved account name becomes the display name.</Text>}
        <TextField label="Business description" multiline onChangeText={setDescription} value={description} />
        <TextField label="Contact phone" keyboardType="phone-pad" onChangeText={setPhone} value={phone} />
        <AddressButton location={address} onPress={() => setShowAddressPicker(true)} />
        <Text style={styles.fieldLabel}>Services to verify</Text>
        <TagPicker selected={categories} onChange={setCategories} options={[...PROVIDER_TAGS]} />
        <View style={styles.sectionHeader}>
          <Text style={styles.fieldLabel}>Service areas</Text>
          <Pressable onPress={() => setShowAreaPicker(true)}><Text style={styles.link}>Add area</Text></Pressable>
        </View>
        <Text style={styles.hint}>Choose every province, city, or district this provider will serve.</Text>
        {areas.map((area) => <View key={area.id} style={styles.fileRow}>
          <MapPin color={colors.primary} size={18} />
          <Text style={styles.flex}>{area.label ?? area.name}</Text>
          <Pressable onPress={() => setAreas((current) => current.filter((item) => item.id !== area.id))}><Trash2 color={colors.danger} size={18} /></Pressable>
        </View>)}
        <FilePicker files={files} onChange={setFiles} />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <PrimaryButton isLoading={isSubmitting} label="Submit service verification" onPress={() => void submit()} />
        <LocationPickerModal onClose={() => setShowAddressPicker(false)} onConfirm={(location) => { setAddress(location); setShowAddressPicker(false); }} value={address} visible={showAddressPicker} />
        <LocationCascadePickerModal allowAnyLevel onClose={() => setShowAreaPicker(false)} onSelect={addArea} value={null} visible={showAreaPicker} />
      </View>}
  </View>;
}

function FilePicker({ files, onChange }: { files: LocalVerificationFile[]; onChange: (files: LocalVerificationFile[]) => void }) {
  const [error, setError] = useState("");
  async function pick() {
    const result = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: true, type: ["application/pdf", "image/png", "image/jpeg"] });
    if (result.canceled) return;
    if (files.length + result.assets.length > MAX_FILES) { setError("You can attach at most 5 files."); return; }
    const invalid = result.assets.find((asset) => (asset.size != null && asset.size > MAX_FILE_SIZE) || (asset.mimeType != null && !ACCEPTED_TYPES.includes(asset.mimeType)));
    if (invalid) { setError("Files must be PDF, PNG, JPG/JPEG and no larger than 5 MB each."); return; }
    setError("");
    onChange([...files, ...result.assets.map((asset) => ({ uri: asset.uri, fileName: asset.name, mimeType: asset.mimeType || "application/octet-stream" }))]);
  }
  return <View style={styles.form}><Text style={styles.fieldLabel}>Verification files (1–5)</Text><Text style={styles.hint}>PDF, PNG or JPG/JPEG. Maximum 5 MB per file.</Text>
    {files.map((file, index) => <View key={`${file.uri}-${index}`} style={styles.fileRow}><FileText color={colors.primary} size={18} /><Text numberOfLines={1} style={styles.flex}>{file.fileName}</Text><Pressable onPress={() => onChange(files.filter((_, itemIndex) => itemIndex !== index))}><Trash2 color={colors.danger} size={18} /></Pressable></View>)}
    <SecondaryButton disabled={files.length >= MAX_FILES} label="Add files" onPress={() => void pick()} />{error ? <Text style={styles.error}>{error}</Text> : null}</View>;
}

function TagPicker({ selected, onChange, options }: { selected: string[]; onChange: (values: string[]) => void; options: string[] }) {
  return <View style={styles.tags}>{options.map((tag) => { const active = selected.includes(tag); return <Pressable key={tag} onPress={() => onChange(active ? selected.filter((item) => item !== tag) : [...selected, tag])} style={[styles.tag, active ? styles.tagActive : null]}>{active ? <Check color={colors.primary} size={14} /> : null}<Text style={[styles.tagText, active ? styles.tagTextActive : null]}>{getProviderTagLabel(tag)}</Text></Pressable>; })}</View>;
}

function ChoiceRow({ options, selected, onSelect }: { options: Array<[string, string]>; selected: string; onSelect: (value: string) => void }) {
  return <View style={styles.tags}>{options.map(([value, label]) => <Pressable key={value} onPress={() => onSelect(value)} style={[styles.tag, selected === value ? styles.tagActive : null]}><Text style={[styles.tagText, selected === value ? styles.tagTextActive : null]}>{label}</Text></Pressable>)}</View>;
}

function AddressButton({ location, onPress }: { location: SelectedLocation | null; onPress: () => void }) {
  return <View style={styles.form}><Text style={styles.fieldLabel}>Business address</Text><Pressable onPress={onPress} style={styles.addressButton}><MapPin color={colors.primary} size={20} /><Text style={styles.flex}>{location?.label || "Select the exact business address"}</Text></Pressable></View>;
}

function ApplicationSummary({ rows, note }: { rows: Array<[string, string]>; note: string }) {
  return <View style={styles.form}>{rows.map(([label, value]) => <ReadOnlyRow key={label} label={label} value={value} />)}<Text style={styles.hint}>{note}</Text></View>;
}
function ReadOnlyRow({ label, value }: { label: string; value: string }) { return <View style={styles.readOnlyRow}><Text style={styles.muted}>{label}</Text><Text style={styles.readOnlyValue}>{value || "-"}</Text></View>; }
function StatusBadge({ status, label }: { status: VerificationStatus; label?: string }) { return <Text style={[styles.badge, status === "approved" ? styles.badgeApproved : status === "rejected" ? styles.badgeRejected : null]}>{label ?? status.replace("_", " ")}</Text>; }
function PayoutStatusBadge({ status }: { status: string }) {
  const label = status === "active" ? "Approved" : status === "rejected" || status === "update_failed" ? "Needs update" : "Not submitted";
  return <Text style={[styles.badge, status === "active" ? styles.badgeApproved : status === "rejected" || status === "update_failed" ? styles.badgeRejected : null]}>{label}</Text>;
}
function documentLabel(value?: string) { return value === "passport" ? "Passport" : value === "national_id" ? "National ID" : "-"; }

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface }, content: { width: "100%", maxWidth: 820, alignSelf: "center", padding: spacing.lg, gap: spacing.md }, loader: { flex: 1 },
  approvedContent: { gap: spacing.md, padding: spacing.lg },
  headerContent: { gap: spacing.lg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md }, title: { color: colors.text, fontSize: 26, fontWeight: "800" }, subtitle: { color: colors.mutedText, marginTop: spacing.xs },
  card: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.background, padding: spacing.lg, gap: spacing.md }, cardHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md }, cardTitle: { color: colors.text, fontSize: 18, fontWeight: "700" },
  stepper: { flexDirection: "row", borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.background, padding: spacing.lg, gap: spacing.lg }, stepItem: { flex: 1, flexDirection: "row", alignItems: "center", gap: spacing.sm, position: "relative" }, stepDot: { width: 34, height: 34, alignItems: "center", justifyContent: "center", borderRadius: 17, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface }, stepDotApproved: { borderColor: colors.primary, backgroundColor: "#E9F7F3" }, stepNumber: { color: colors.mutedText, fontWeight: "800" }, stepNumberApproved: { color: colors.primary }, stepCopy: { flex: 1, alignItems: "flex-start", gap: spacing.xs }, stepConnector: { position: "absolute", right: -spacing.lg, width: spacing.lg, height: 1, backgroundColor: colors.border }, progressLabel: { color: colors.text, fontWeight: "700" },
  badge: { overflow: "hidden", borderRadius: 999, backgroundColor: "#FFF4D6", color: "#8A5A00", paddingHorizontal: spacing.sm, paddingVertical: spacing.xs, fontSize: 12, fontWeight: "700", textTransform: "capitalize" }, badgeApproved: { backgroundColor: "#E9F7F3", color: colors.primary }, badgeRejected: { backgroundColor: "#FDECEC", color: colors.danger },
  form: { gap: spacing.md }, fieldLabel: { color: colors.text, fontSize: 14, fontWeight: "600" }, hint: { color: colors.mutedText, fontSize: 13, lineHeight: 19 }, error: { color: colors.danger, fontSize: 14, lineHeight: 20 }, rejection: { borderRadius: radius.sm, backgroundColor: "#FDECEC", color: colors.danger, padding: spacing.md },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }, tag: { minHeight: 40, flexDirection: "row", alignItems: "center", gap: spacing.xs, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md }, tagActive: { borderColor: colors.primary, backgroundColor: "#E9F7F3" }, tagText: { color: colors.text, fontWeight: "600" }, tagTextActive: { color: colors.primary },
  fileRow: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: spacing.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: spacing.md }, addressButton: { minHeight: 54, flexDirection: "row", alignItems: "center", gap: spacing.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md },
  readOnlyRow: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border, paddingBottom: spacing.sm }, readOnlyValue: { flex: 1, color: colors.text, fontWeight: "600", textAlign: "right" }, muted: { color: colors.mutedText }, link: { color: colors.primary, fontWeight: "700" }, flex: { flex: 1, color: colors.text }, completeIcon: { alignSelf: "center", width: 68, height: 68, alignItems: "center", justifyContent: "center", borderRadius: 34, backgroundColor: "#E9F7F3" }, completeTitle: { color: colors.text, fontSize: 22, fontWeight: "800", textAlign: "center" }, completeText: { color: colors.mutedText, fontSize: 14, lineHeight: 21, textAlign: "center" },
  profileSummaryCard: { flexDirection: "row", flexWrap: "wrap", alignItems: "flex-start", gap: spacing.lg, borderWidth: 1, borderColor: colors.border, borderRadius: 18, backgroundColor: colors.background, padding: spacing.lg },
  profileSummaryMain: { flex: 1, minWidth: 260, gap: spacing.sm },
  businessTitleRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm },
  businessName: { color: colors.text, fontSize: 24, fontWeight: "800" },
  serviceVerifiedBadge: { overflow: "hidden", borderRadius: 999, backgroundColor: "#E9F7F3", color: colors.primary, paddingHorizontal: spacing.sm, paddingVertical: 5, fontSize: 12, fontWeight: "800" },
  statusRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  statusBadge: { minHeight: 26, flexDirection: "row", alignItems: "center", gap: spacing.xs, borderWidth: 1, borderColor: colors.border, borderRadius: 999, backgroundColor: colors.surface, paddingHorizontal: spacing.sm },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusDotActive: { backgroundColor: colors.primary },
  statusDotInactive: { backgroundColor: "#A0A4AE" },
  statusBadgeText: { color: colors.mutedText, fontSize: 12, fontWeight: "800" },
  bioText: { color: colors.text, fontSize: 15, lineHeight: 22 },
  metaText: { color: colors.mutedText, fontSize: 13, lineHeight: 19 },
  tagWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  serviceTag: { borderRadius: 999, backgroundColor: colors.surface, paddingHorizontal: spacing.sm, paddingVertical: 5 },
  serviceTagText: { color: colors.text, fontSize: 12, fontWeight: "700" },
  settingsButton: { minWidth: 190, minHeight: 52, alignItems: "center", justifyContent: "center", borderRadius: radius.md, backgroundColor: colors.primary, paddingHorizontal: spacing.lg },
  settingsButtonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { color: colors.text, fontSize: 20, fontWeight: "800" },
  moreButton: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  moreText: { color: colors.primary, fontSize: 15, fontWeight: "700" },
  portfolioGap: { width: spacing.md },
  reviewCard: { gap: spacing.sm, borderWidth: 1, borderColor: colors.border, borderRadius: 14, backgroundColor: colors.background, padding: spacing.md },
  reviewTopRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  ratingText: { color: colors.text, fontSize: 15, fontWeight: "800" },
  reviewDate: { color: colors.mutedText, fontSize: 13 },
  reviewComment: { color: colors.text, fontSize: 15, lineHeight: 22 },
  emptyText: { color: colors.mutedText, fontSize: 14, lineHeight: 21 },
  footerLoader: { paddingVertical: spacing.lg },
});
