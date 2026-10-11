const assert = require("node:assert/strict");
const test = require("node:test");

const {
  chooseCity,
  chooseDistrict,
  chooseProvince,
  getCompletedLocation,
} = require("../../../../.test-build/features/locations/location-cascade-state.js");

const istanbul = {
  id: 1,
  parent_id: null,
  code: "tr-istanbul",
  name: "Istanbul",
  level: "province",
};
const istanbulCity = {
  id: 2,
  parent_id: 1,
  code: "tr-istanbul-city",
  name: "Istanbul",
  level: "city",
};
const kadikoy = {
  id: 3,
  parent_id: 2,
  code: "tr-istanbul-city-kadikoy",
  name: "Kadikoy",
  level: "district",
};
const ankara = { ...istanbul, id: 4, code: "tr-ankara", name: "Ankara" };

test("choosing a province clears the previous city and district", () => {
  const current = {
    province: istanbul,
    city: istanbulCity,
    district: kadikoy,
  };

  assert.deepEqual(chooseProvince(current, ankara), {
    province: ankara,
    city: null,
    district: null,
  });
});

test("choosing a city clears the previous district", () => {
  const current = {
    province: istanbul,
    city: istanbulCity,
    district: kadikoy,
  };
  const ankaraCity = {
    ...istanbulCity,
    id: 5,
    parent_id: ankara.id,
    code: "tr-ankara-city",
    name: "Ankara",
  };

  assert.deepEqual(chooseCity(chooseProvince(current, ankara), ankaraCity), {
    province: ankara,
    city: ankaraCity,
    district: null,
  });
});

test("a completed cascade stores the district id and province name", () => {
  const completed = chooseDistrict(
    { province: istanbul, city: istanbulCity, district: null },
    kadikoy,
  );

  assert.deepEqual(getCompletedLocation(completed), {
    serviceLocationId: kadikoy.id,
    serviceProvince: istanbul.name,
    label: "Istanbul / Istanbul / Kadikoy",
  });
});

test("province or city selections alone cannot be submitted", () => {
  assert.equal(
    getCompletedLocation({
      province: istanbul,
      city: istanbulCity,
      district: null,
    }),
    null,
  );
});

test("operating settings can select a whole province or city", () => {
  assert.deepEqual(
    getCompletedLocation(
      { province: istanbul, city: null, district: null },
      true,
    ),
    {
      serviceLocationId: istanbul.id,
      serviceProvince: istanbul.name,
      label: "Istanbul",
    },
  );
  assert.deepEqual(
    getCompletedLocation(
      { province: istanbul, city: istanbulCity, district: null },
      true,
    ),
    {
      serviceLocationId: istanbulCity.id,
      serviceProvince: istanbul.name,
      label: "Istanbul / Istanbul",
    },
  );
});
