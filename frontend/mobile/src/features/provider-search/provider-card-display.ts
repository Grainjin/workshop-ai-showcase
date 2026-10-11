export type ProviderCardStatus = {
  label: "Open" | "Closed" | "Online" | "Offline";
  tone: "active" | "inactive";
};

export function getProviderCardImageUrl({
  avatarUrl,
  portfolioImageUrl,
}: {
  avatarUrl?: string | null;
  portfolioImageUrl?: string | null;
}) {
  return avatarUrl || portfolioImageUrl || null;
}

export function getProviderCardStatus({
  isOpen,
  isOnline,
}: {
  isOpen?: boolean;
  isOnline: boolean;
}): ProviderCardStatus {
  if (typeof isOpen === "boolean") {
    return {
      label: isOpen ? "Open" : "Closed",
      tone: isOpen ? "active" : "inactive",
    };
  }

  return {
    label: isOnline ? "Online" : "Offline",
    tone: isOnline ? "active" : "inactive",
  };
}

export function formatProviderDistance(distanceKm?: number | null) {
  if (distanceKm == null || !Number.isFinite(distanceKm)) return null;
  return `${distanceKm.toFixed(1)} km away`;
}
