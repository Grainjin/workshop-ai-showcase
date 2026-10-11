from backend import models
from backend.utils.service_locations import seed_service_locations
from tests.conftest import register_session


def location_by_name(db_session, name, level, parent_id=None):
    query = db_session.query(models.ServiceLocation).filter(
        models.ServiceLocation.name == name,
        models.ServiceLocation.level == level,
    )
    if parent_id is None:
        query = query.filter(models.ServiceLocation.parent_id.is_(None))
    else:
        query = query.filter(models.ServiceLocation.parent_id == parent_id)
    return query.one()


def test_locations_endpoint_lists_turkish_hierarchy(client, db_session):
    seed_service_locations(db_session)
    db_session.commit()

    provinces = client.get("/locations")
    assert provinces.status_code == 200, provinces.text
    province_items = provinces.json()["data"]["items"]
    assert len(province_items) == 81
    assert {item["level"] for item in province_items} == {"province"}

    istanbul = location_by_name(db_session, "Istanbul", "province")
    detail = client.get(f"/locations/{istanbul.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"] == {
        "id": istanbul.id,
        "parent_id": None,
        "code": "tr-istanbul",
        "name": "Istanbul",
        "level": "province",
    }

    cities = client.get("/locations", params={"parent_id": istanbul.id})
    assert cities.status_code == 200, cities.text
    city_items = cities.json()["data"]["items"]
    assert len(city_items) == 1
    assert city_items[0]["level"] == "city"
    assert city_items[0]["parent_id"] == istanbul.id

    districts = client.get(
        "/locations",
        params={"parent_id": city_items[0]["id"]},
    )
    assert districts.status_code == 200, districts.text
    district_names = {item["name"] for item in districts.json()["data"]["items"]}
    assert {"Kadikoy", "Uskudar"}.issubset(district_names)


def test_locations_endpoint_rejects_unknown_parent(client):
    response = client.get("/locations", params={"parent_id": 999999})
    assert response.status_code == 404
    assert response.json()["error"]["detail"] == "Service location not found"


def test_customer_profile_stores_selected_district_and_derived_province(
    client, db_session
):
    seeded = seed_service_locations(db_session)
    db_session.commit()
    district = seeded["tr-istanbul-city-kadikoy"]
    customer = register_session(client, "location-customer@example.com")

    response = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551110001",
            "address": "Kadikoy",
            "service_province": "not-authoritative",
            "service_location_id": district.id,
        },
        headers=customer["headers"],
    )

    assert response.status_code == 200, response.text
    profile = response.json()["data"]["profile"]
    assert profile["service_location_id"] == district.id
    assert profile["service_province"] == "Istanbul"


def test_provider_search_accepts_province_and_exact_district_scope(
    client, db_session, marketplace
):
    seeded = seed_service_locations(db_session)
    db_session.commit()
    provider = db_session.query(models.ProviderProfile).filter(
        models.ProviderProfile.id == marketplace["provider_profile"]["id"]
    ).one()
    provider.service_location_id = seeded["tr-istanbul-city-kadikoy"].id
    provider.service_province = "Istanbul"
    db_session.commit()

    province_response = client.get(
        "/providers",
        params={"service_location_id": seeded["tr-istanbul"].id},
    )
    assert province_response.status_code == 200, province_response.text
    assert any(
        item["id"] == provider.id
        for item in province_response.json()["data"]["items"]
    )

    district_response = client.get(
        "/providers",
        params={"service_location_id": seeded["tr-istanbul-city-kadikoy"].id},
    )
    assert district_response.status_code == 200, district_response.text
    assert [item["id"] for item in district_response.json()["data"]["items"]] == [
        provider.id
    ]
