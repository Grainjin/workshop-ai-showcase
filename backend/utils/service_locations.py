from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query, Session

from backend import models
from backend.location_data import iter_location_seeds

VALID_LOCATION_LEVELS = {"province", "city", "district"}


def normalize_location_name(value: str | None):
    if value is None:
        return None
    return value.strip().casefold()


def seed_service_locations(db: Session):
    existing = {
        location.code: location
        for location in db.query(models.ServiceLocation).all()
    }
    seeded = {}
    for item in iter_location_seeds():
        location = existing.get(item.code)
        if location is None:
            location = models.ServiceLocation(
                code=item.code,
                name=item.name,
                level=item.level,
                parent_id=seeded[item.parent_code].id if item.parent_code else None,
            )
            db.add(location)
            db.flush()
        else:
            location.name = item.name
            location.level = item.level
            location.parent_id = seeded[item.parent_code].id if item.parent_code else None
        seeded[item.code] = location
    return seeded


def get_location(db: Session, location_id: int):
    location = (
        db.query(models.ServiceLocation)
        .filter(models.ServiceLocation.id == location_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Service location not found")
    if location.level not in VALID_LOCATION_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid service location level")
    return location


def get_location_chain(db: Session, location: models.ServiceLocation):
    chain = []
    current = location
    while current is not None:
        chain.append(current)
        if current.parent_id is None:
            break
        current = get_location(db, current.parent_id)
    return list(reversed(chain))


def format_service_area(db: Session, location: models.ServiceLocation):
    return {
        "id": location.id,
        "name": location.name,
        "level": location.level,
        "label": " / ".join(item.name for item in get_location_chain(db, location)),
    }


def get_province_for_location(db: Session, location: models.ServiceLocation):
    return get_location_chain(db, location)[0]


def resolve_location_context(
    db: Session,
    *,
    requested_province: str | None = None,
    requested_location_id: int | None = None,
    profile_province: str | None = None,
    profile_location_id: int | None = None,
):
    """Resolve request/profile location values as one consistent context."""
    has_explicit_province = requested_province is not None
    resolved_province = (
        requested_province.strip()
        if has_explicit_province
        else (profile_province.strip() if profile_province else None)
    )
    resolved_location_id = requested_location_id

    if resolved_location_id is None and not has_explicit_province:
        resolved_location_id = profile_location_id

    if resolved_location_id is not None:
        location = get_location(db, resolved_location_id)
        location_province = get_province_for_location(db, location)
        if (
            has_explicit_province
            and normalize_location_name(resolved_province)
            != normalize_location_name(location_province.name)
        ):
            raise HTTPException(
                status_code=400,
                detail="service_location_id does not belong to service_province",
            )
        if not has_explicit_province:
            resolved_province = location_province.name

    return resolved_province, resolved_location_id


def location_scope_ids(db: Session, location_id: int):
    selected = get_location(db, location_id)
    locations = db.query(models.ServiceLocation).all()
    children_by_parent = defaultdict(list)
    for location in locations:
        if location.parent_id is not None:
            children_by_parent[location.parent_id].append(location.id)

    scope = {selected.id}
    frontier = [selected.id]
    while frontier:
        parent_id = frontier.pop()
        children = children_by_parent[parent_id]
        scope.update(children)
        frontier.extend(children)
    return scope


def location_ancestor_ids(db: Session, location_id: int):
    selected = get_location(db, location_id)
    return {location.id for location in get_location_chain(db, selected)}


def validate_profile_location(
    db: Session,
    location_id: int | None,
):
    if location_id is None:
        return None
    location = get_location(db, location_id)
    if location.level != "district":
        raise HTTPException(
            status_code=400,
            detail="Provider and customer service location must be a district",
        )
    return location


def apply_profile_location(profile, db: Session, location_id: int | None):
    location = validate_profile_location(db, location_id)
    if location is None:
        return None
    profile.service_location_id = location.id
    profile.service_province = get_province_for_location(db, location).name
    return location


def filter_provider_query_by_location(
    query: Query,
    db: Session,
    *,
    location_id: int | None = None,
    province_name: str | None = None,
):
    if location_id is not None:
        selected = get_location(db, location_id)
        scoped_ids = location_scope_ids(db, location_id)
        accepted_area_ids = scoped_ids | location_ancestor_ids(db, location_id)
        province = get_province_for_location(db, selected)
        normalized_province = normalize_location_name(province.name)
        return query.filter(
            or_(
                models.ProviderProfile.id.in_(
                    db.query(models.ProviderServiceArea.provider_profile_id).filter(
                        models.ProviderServiceArea.service_location_id.in_(accepted_area_ids)
                    )
                ),
                models.ProviderProfile.service_location_id.in_(scoped_ids),
                and_(
                    models.ProviderProfile.service_location_id.is_(None),
                    func.lower(func.trim(models.ProviderProfile.service_province))
                    == normalized_province,
                ),
            )
        )

    if province_name:
        normalized_province_name = normalize_location_name(province_name)
        province = (
            db.query(models.ServiceLocation)
            .filter(
                models.ServiceLocation.level == "province",
                func.lower(func.trim(models.ServiceLocation.name))
                == normalized_province_name,
            )
            .first()
        )
        if province:
            scoped_ids = location_scope_ids(db, province.id)
            return query.filter(
                or_(
                    models.ProviderProfile.id.in_(
                        db.query(models.ProviderServiceArea.provider_profile_id).filter(
                            models.ProviderServiceArea.service_location_id.in_(scoped_ids)
                        )
                    ),
                    models.ProviderProfile.service_location_id.in_(scoped_ids),
                    (
                        models.ProviderProfile.service_location_id.is_(None)
                        & (
                            func.lower(func.trim(models.ProviderProfile.service_province))
                            == normalized_province_name
                        )
                    ),
                )
            )
        return query.filter(
            func.lower(func.trim(models.ProviderProfile.service_province)).contains(
                normalized_province_name
            )
        )

    return query


def profile_matches_location(
    profile,
    db: Session,
    *,
    location_id: int | None = None,
    province_name: str | None = None,
):
    if location_id is not None:
        selected = get_location(db, location_id)
        accepted_area_ids = location_scope_ids(db, location_id) | location_ancestor_ids(
            db, location_id
        )
        has_area = (
            db.query(models.ProviderServiceArea.id)
            .filter(
                models.ProviderServiceArea.provider_profile_id == profile.id,
                models.ProviderServiceArea.service_location_id.in_(accepted_area_ids),
            )
            .first()
        )
        if has_area:
            return True
        if profile.service_location_id in location_scope_ids(db, location_id):
            return True
        return (
            profile.service_location_id is None
            and normalize_location_name(profile.service_province)
            == normalize_location_name(get_province_for_location(db, selected).name)
        )
    if province_name:
        return normalize_location_name(province_name) in normalize_location_name(
            profile.service_province
        )
    return True


def format_location_response(location):
    return {
        "id": location.id,
        "parent_id": location.parent_id,
        "code": location.code,
        "name": location.name,
        "level": location.level,
    }
