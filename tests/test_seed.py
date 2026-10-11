from backend.constants import ALLOWED_PROVIDER_TAGS
from backend.seed_demo_data import pick_provider_tags


def test_review_seed_is_repeatable_configurable_and_does_not_change_global_rng(monkeypatch):
    import random
    from backend import config
    from backend.seed_demo_data import pick_reviews

    state = random.getstate()
    monkeypatch.setattr(config, "WORKSHOP_DEMO_SEED", 42)
    first = pick_reviews()
    assert pick_reviews() == first
    monkeypatch.setattr(config, "WORKSHOP_DEMO_SEED", 43)
    assert pick_reviews() != first
    assert random.getstate() == state


def test_seed_tag_picker_stays_in_allowed_set():
    for index in range(40):
        tags = pick_provider_tags(index)
        assert tags
        assert all(tag in ALLOWED_PROVIDER_TAGS for tag in tags)


def test_demo_seed_repairs_only_mapped_provider_payout_readiness(db_session, monkeypatch):
    from backend import config, models
    from backend.constants import DEMO_USER_EMAILS
    from backend.seed_demo_data import seed_demo_data
    monkeypatch.setattr(config, "DEMO_MODE", True)
    seed_demo_data(db_session)
    db_session.commit()
    provider = db_session.query(models.ProviderProfile).join(models.User).filter(
        models.User.email == DEMO_USER_EMAILS["provider"]).one()
    payout = db_session.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider.id).one()
    assert payout.status == "active"
    assert payout.submerchant_external_id == f"demo-provider-{provider.id}"
    assert payout.submerchant_key is None
    assert payout.iban is None
    services = db_session.query(models.ProviderApprovedService).filter_by(provider_profile_id=provider.id).all()
    assert sorted(row.service_category for row in services) == sorted(provider.tags.split(","))
    assert all(row.is_enabled for row in services)
    area = db_session.query(models.ProviderServiceArea).filter_by(provider_profile_id=provider.id).one()
    assert area.service_location_id == provider.service_location_id
    others = db_session.query(models.ProviderSubmerchant).filter(models.ProviderSubmerchant.id != payout.id).all()
    assert all(row.status == "draft" for row in others)
    payout.status = "rejected"
    payout.submerchant_key = "drifted-external-key"
    payout.iban = "drifted-bank-account"
    payout.iyzico_error_code = "error"
    provider.qualification_verification_status = "rejected"
    services[0].is_enabled = False
    db_session.delete(area)
    db_session.commit()
    seed_demo_data(db_session)
    db_session.commit()
    assert payout.status == "active"
    assert payout.submerchant_key is None and payout.iban is None
    assert payout.iyzico_error_code is None
    assert provider.qualification_verification_status == "approved"
    assert all(row.is_enabled for row in db_session.query(models.ProviderApprovedService)
               .filter_by(provider_profile_id=provider.id))
    assert db_session.query(models.ProviderServiceArea).filter_by(provider_profile_id=provider.id).count() == 1
    assert db_session.query(models.ProviderSubmerchant).count() == 26


def test_normal_seed_keeps_payout_drafts(db_session, monkeypatch):
    from backend import config, models
    from backend.seed_demo_data import seed_demo_data
    monkeypatch.setattr(config, "DEMO_MODE", False)
    seed_demo_data(db_session)
    db_session.commit()
    assert all(row.status == "draft" and row.submerchant_key is None
               for row in db_session.query(models.ProviderSubmerchant).all())
    assert db_session.query(models.ProviderApprovedService).count() == 0
