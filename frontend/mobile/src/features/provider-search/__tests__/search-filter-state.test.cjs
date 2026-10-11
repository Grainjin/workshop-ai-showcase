const assert = require("node:assert/strict");
const test = require("node:test");

const {
  buildProviderSearchParams,
  countActiveSearchFilters,
  createDefaultSearchFilters,
  getSearchFilterSummary,
  getSearchFilterValidationError,
  hasCustomerSearchCoordinates,
  parseOptionalNonNegativeInteger,
  restoreInitialSearchFilters,
} = require("../../../../.test-build/search-filter-state.js");

test("search filters map to the provider search query contract", () => {
  assert.deepEqual(
    buildProviderSearchParams({
      ...createDefaultSearchFilters(),
      category: "plumbing",
      maxDistanceKm: 10,
      minPrice: "50",
      maxPrice: "150",
      minRating: 4.5,
      availability: "open",
      sort: "highestRating",
    }),
    {
      tags: "plumbing",
      max_distance_km: 10,
      min_price: 50,
      max_price: 150,
      min_rating: 4.5,
      is_open: true,
      sort_by: "highest_rating",
    },
  );
});

test("default filters do not send optional query parameters", () => {
  assert.deepEqual(buildProviderSearchParams(createDefaultSearchFilters()), {});
});

test("sort options use the aliases accepted by provider search", () => {
  assert.equal(
    buildProviderSearchParams({
      ...createDefaultSearchFilters(),
      sort: "nearest",
    }).sort_by,
    "nearest",
  );
  assert.equal(
    buildProviderSearchParams({
      ...createDefaultSearchFilters(),
      sort: "lowestPrice",
    }).sort_by,
    "lowest_price",
  );
});

test("availability maps both open and closed states to provider search", () => {
  assert.equal(
    buildProviderSearchParams({
      ...createDefaultSearchFilters(),
      availability: "open",
    }).is_open,
    true,
  );
  assert.equal(
    buildProviderSearchParams({
      ...createDefaultSearchFilters(),
      availability: "closed",
    }).is_open,
    false,
  );
});

test("default search filters have no active refinements", () => {
  const filters = createDefaultSearchFilters();

  assert.deepEqual(filters, {
    category: null,
    maxDistanceKm: null,
    minPrice: "",
    maxPrice: "",
    minRating: null,
    availability: "any",
    sort: "recommended",
  });
  assert.equal(countActiveSearchFilters(filters), 0);
});

test("a category selected on Home seeds the result-page category filter", () => {
  const filters = createDefaultSearchFilters("plumbing");

  assert.equal(filters.category, "plumbing");
  assert.equal(countActiveSearchFilters(filters), 1);
});

test("clearing restores the category carried over from Home", () => {
  assert.deepEqual(restoreInitialSearchFilters("plumbing"), {
    category: "plumbing",
    maxDistanceKm: null,
    minPrice: "",
    maxPrice: "",
    minRating: null,
    availability: "any",
    sort: "recommended",
  });
});

test("distance controls require one complete customer coordinate pair", () => {
  assert.equal(hasCustomerSearchCoordinates(null), false);
  assert.equal(
    hasCustomerSearchCoordinates({
      current_latitude: 41,
      current_longitude: null,
      default_service_latitude: null,
      default_service_longitude: null,
      latitude: null,
      longitude: null,
    }),
    false,
  );
  assert.equal(
    hasCustomerSearchCoordinates({
      current_latitude: null,
      current_longitude: null,
      default_service_latitude: 0,
      default_service_longitude: 0,
      latitude: null,
      longitude: null,
    }),
    true,
  );
});

test("collapsed filter summary reports the active count and sort", () => {
  assert.equal(
    getSearchFilterSummary(createDefaultSearchFilters()),
    "All providers · Recommended",
  );
  assert.equal(
    getSearchFilterSummary({
      ...createDefaultSearchFilters("plumbing"),
      maxDistanceKm: 10,
      sort: "nearest",
    }),
    "3 filters · Nearest",
  );
});

test("active filter count treats price range and sort as separate controls", () => {
  const filters = {
    ...createDefaultSearchFilters(),
    category: "plumbing",
    minPrice: "50",
    maxPrice: "150",
    availability: "open",
    sort: "nearest",
  };

  assert.equal(countActiveSearchFilters(filters), 4);
});

test("optional hourly prices accept only non-negative whole numbers", () => {
  assert.equal(parseOptionalNonNegativeInteger(""), undefined);
  assert.equal(parseOptionalNonNegativeInteger(" 12 "), 12);
  assert.equal(parseOptionalNonNegativeInteger("12.5"), undefined);
  assert.equal(parseOptionalNonNegativeInteger("-1"), undefined);
  assert.equal(parseOptionalNonNegativeInteger("abc"), undefined);
});

test("price validation rejects malformed and reversed ranges", () => {
  assert.equal(
    getSearchFilterValidationError({
      ...createDefaultSearchFilters(),
      minPrice: "free",
    }),
    "Enter a valid hourly price.",
  );
  assert.equal(
    getSearchFilterValidationError({
      ...createDefaultSearchFilters(),
      minPrice: "200",
      maxPrice: "100",
    }),
    "Minimum price cannot exceed maximum price.",
  );
  assert.equal(
    getSearchFilterValidationError({
      ...createDefaultSearchFilters(),
      minPrice: "50",
      maxPrice: "100",
    }),
    null,
  );
});
