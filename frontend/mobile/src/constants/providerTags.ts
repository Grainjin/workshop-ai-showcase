export const PROVIDER_TAGS = [
  "cleaning",
  "childcare",
  "elderly_care",
  "electrician",
  "plumbing",
  "painter",
  "locksmith",
  "technician",
  "moving",
  "other",
] as const;

export type ProviderTag = (typeof PROVIDER_TAGS)[number];

export const PROVIDER_TAG_LABELS: Record<ProviderTag, string> = {
  cleaning: "Cleaning",
  childcare: "Childcare",
  elderly_care: "Elderly care",
  electrician: "Electrician",
  plumbing: "Plumbing",
  painter: "Painter",
  locksmith: "Locksmith",
  technician: "Technician",
  moving: "Moving",
  other: "Other",
};

export const DEFAULT_PROVIDER_TAG: ProviderTag = "cleaning";

export function getProviderTagLabel(tag: string) {
  return PROVIDER_TAG_LABELS[tag as ProviderTag] ?? tag;
}
