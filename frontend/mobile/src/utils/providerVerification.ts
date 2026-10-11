import type { ProviderProfile } from "../types/provider";

/**
 * Provider identity and qualification are independently submitted and
 * reviewed. Order eligibility also depends on the separate payout account;
 * this helper describes the two verification applications only.
 *
 * Older responses that only expose verification_status are still supported:
 * both steps fall back to that value while newer responses expose the two
 * independent statuses explicitly.
 */
export type VerificationStatus =
  | "not_submitted"
  | "approved"
  | "pending"
  | "rejected";

/**
 * The two applications are independent, so qualification is never locked by
 * the identity application state.
 */
export type StepState = VerificationStatus;

function normalise(value: string | null | undefined): VerificationStatus {
  if (
    value === "not_submitted" ||
    value === "approved" ||
    value === "rejected"
  ) {
    return value;
  }

  return "pending";
}

export function getIdentityStatus(
  profile: ProviderProfile | null,
): VerificationStatus {
  if (!profile) {
    return "not_submitted";
  }

  return normalise(
    profile.identity_verification_status ?? profile.verification_status,
  );
}

export function getQualificationStatus(
  profile: ProviderProfile | null,
): VerificationStatus {
  if (!profile) {
    return "not_submitted";
  }

  return normalise(
    profile.qualification_verification_status ?? profile.verification_status,
  );
}

export function getQualificationStepState(
  profile: ProviderProfile | null,
): StepState {
  return getQualificationStatus(profile);
}

export function isQualificationApproved(profile: ProviderProfile | null) {
  return getQualificationStatus(profile) === "approved";
}

export function describeStatus(status: StepState) {
  if (status === "approved") {
    return "Approved";
  }

  if (status === "rejected") {
    return "Not approved";
  }

  return status === "not_submitted" ? "Not submitted" : "Under review";
}

/**
 * The backend cannot tell "never submitted" from "submitted and waiting", so
 * the action says what it does to an existing submission rather than implying
 * the step has not started.
 */
export function describeStepAction(state: StepState, step: "identity" | "qualification") {
  if (state === "approved") {
    return null;
  }

  if (state === "rejected") {
    return "Resubmit";
  }

  if (state === "not_submitted") {
    return step === "identity" ? "Identity details" : "Service details";
  }

  return "Under review";
}
