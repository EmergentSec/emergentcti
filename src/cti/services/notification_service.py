import logging

from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.alert import AlertEvent, AlertRule
from cti.services.webhook_service import dispatch_webhook

logger = logging.getLogger(__name__)


async def send_alert_notification(
    db: AsyncSession, alert_event: AlertEvent, rule: AlertRule
) -> None:
    """Dispatch notifications for a triggered alert event.

    Iterates over the rule's notification_channels and dispatches
    the appropriate notification for each channel type.
    Currently supported channel types:
      - "webhook": dispatches an alert.triggered webhook event
    """
    channels = rule.notification_channels or []
    errors: list[str] = []

    for channel in channels:
        channel_type = channel.get("type") if isinstance(channel, dict) else None

        if channel_type == "webhook":
            try:
                payload = {
                    "alert_event_id": str(alert_event.id),
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "observable_id": str(alert_event.observable_id),
                }
                await dispatch_webhook(db, "alert.triggered", payload)
            except Exception as e:
                logger.error(
                    "Webhook notification failed for alert event %s: %s",
                    alert_event.id,
                    e,
                    exc_info=True,
                )
                errors.append(f"webhook: {e}")
        else:
            logger.warning(
                "Unknown notification channel type %r in rule %s",
                channel_type,
                rule.id,
            )

    # Update alert event notification status
    if errors:
        alert_event.notification_sent = False
        alert_event.notification_error = "; ".join(errors)
    else:
        alert_event.notification_sent = True
        alert_event.notification_error = None

    await db.flush()
