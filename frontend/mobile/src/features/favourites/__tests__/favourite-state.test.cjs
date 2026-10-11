const assert = require("node:assert/strict");
const test = require("node:test");

const {
  appendFavouritePage,
  removeFavouriteByProviderId,
  setProviderFavouriteState,
} = require("../../../../.test-build/features/favourites/favourite-state.js");

const provider = {
  id: 7,
  user_id: 70,
  business_name: "Istanbul Plumbing",
  bio: "Emergency plumbing",
  phone_number: "+905551110001",
  address: "Kadikoy",
  service_province: "Istanbul",
  latitude: 41.0,
  longitude: 29.0,
  service_radius_km: 20,
  tags: ["plumbing"],
  certificate_name: "Licence",
  certificate_url: "/media/licence.pdf",
  certificate_files: [],
  hourly_rate: 500,
  experience_years: 8,
  verification_status: "approved",
  verification_note: null,
  notes: null,
  is_online: true,
  average_rating: 4.8,
  review_count: 24,
  distance_km: 2.5,
};

const firstFavourite = {
  id: 11,
  customer_id: 3,
  provider_profile_id: 7,
  created_at: "2026-09-13T00:00:00Z",
  provider,
};

test("setProviderFavouriteState changes only the detail favourite flag", () => {
  const detail = {
    provider: { ...provider, is_open: true, is_favorited: false },
    history: {
      id: 4,
      customer_id: 3,
      last_provider_profile_id: 7,
      last_provider_tag: "plumbing",
      updated_at: "2026-09-13T00:00:00Z",
    },
  };

  const updated = setProviderFavouriteState(detail, true);

  assert.equal(updated.provider.is_favorited, true);
  assert.equal(updated.provider.is_open, true);
  assert.deepEqual(updated.history, detail.history);
  assert.notEqual(updated, detail);
});

test("removeFavouriteByProviderId removes only the matching provider", () => {
  const secondFavourite = {
    ...firstFavourite,
    id: 12,
    provider_profile_id: 8,
    provider: { ...provider, id: 8 },
  };

  assert.deepEqual(
    removeFavouriteByProviderId([firstFavourite, secondFavourite], 7),
    [secondFavourite],
  );
});

test("appendFavouritePage keeps the first occurrence of duplicate records", () => {
  const nextFavourite = {
    ...firstFavourite,
    id: 12,
    provider_profile_id: 8,
    provider: { ...provider, id: 8 },
  };

  assert.deepEqual(
    appendFavouritePage([firstFavourite], [firstFavourite, nextFavourite]),
    [firstFavourite, nextFavourite],
  );
});
