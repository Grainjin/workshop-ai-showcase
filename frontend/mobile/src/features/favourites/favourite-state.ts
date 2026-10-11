import type {
  CustomerProviderDetail,
  FavoriteProvider,
} from "../../types/provider";

export function setProviderFavouriteState(
  detail: CustomerProviderDetail,
  isFavorited: boolean,
): CustomerProviderDetail {
  return {
    ...detail,
    provider: {
      ...detail.provider,
      is_favorited: isFavorited,
    },
  };
}

export function removeFavouriteByProviderId(
  favourites: FavoriteProvider[],
  providerProfileId: number,
): FavoriteProvider[] {
  return favourites.filter(
    (favourite) => favourite.provider_profile_id !== providerProfileId,
  );
}

export function appendFavouritePage(
  current: FavoriteProvider[],
  incoming: FavoriteProvider[],
): FavoriteProvider[] {
  const seen = new Set(current.map((favourite) => favourite.id));
  const additions = incoming.filter((favourite) => {
    if (seen.has(favourite.id)) {
      return false;
    }
    seen.add(favourite.id);
    return true;
  });

  return [...current, ...additions];
}
