"""Workerless demo keeps durable in-app notifications without queueing delivery."""

from types import SimpleNamespace
import pytest

from backend import config, models
from backend.schemas import NotificationRelatedType, NotificationType
from backend.utils.notification import create_notification
from backend.utils.notification_queue import deliver_notification_task, enqueue_notification_delivery


@pytest.mark.parametrize("enabled", [True, False])
def test_notification_persists_and_only_normal_mode_queues(marketplace, db_session, monkeypatch, enabled):
    calls = []

    def queue(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id="notification-worker-job")

    monkeypatch.setattr(config, "DEMO_MODE", enabled)
    # The general marketplace fixture stubs this boundary. Restore the real helper.
    monkeypatch.setattr("backend.utils.notification.enqueue_notification_delivery", enqueue_notification_delivery)
    monkeypatch.setattr(deliver_notification_task, "apply_async", queue)
    create_notification(marketplace["customer"]["user"]["id"], "Demo notice", "Simulated notice",
        NotificationType.booking_completed_by_provider, NotificationRelatedType.booking, 12, db_session)
    db_session.commit()
    notification = db_session.query(models.Notification).one()
    assert notification.title == "Demo notice" and notification.content == "Simulated notice"
    assert len(calls) == (0 if enabled else 1)
    assert db_session.query(models.AsyncTask).count() == (0 if enabled else 1)
