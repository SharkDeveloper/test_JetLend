"""
Celery tasks for asynchronous email delivery.

Each ``MailingRecord`` is dispatched as an independent task so that:
- a single slow/failing send does not block the rest of the queue;
- the import command returns immediately after persisting all records;
- failed tasks are visible in the DB for retry/alerting.

Retry strategy
──────────────
The task catches all unexpected exceptions, logs them, and marks the record
as FAILED so that an operator or a separate retry command can re-queue it.
We avoid Celery's ``self.retry()`` mechanism here because its behaviour in
TASK_ALWAYS_EAGER mode (used in tests) is broker-dependent and hard to test
reliably.  The trade-off is explicit and intentional.
"""

import logging

from celery import shared_task
from django.db import transaction

from .email_sender import send_email
from .models import MailingRecord, MailingStatus

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,           # re-queue if the worker crashes mid-task
    reject_on_worker_lost=True,
)
def dispatch_mailing(self, mailing_id: int) -> None:
    """
    Fetch a MailingRecord and deliver its email.

    Transitions: PENDING → SENDING → SENT  (or FAILED on any exception).

    A row-level lock (``select_for_update``) inside the initial transaction
    prevents two workers from delivering the same message concurrently.
    """
    try:
        with transaction.atomic():
            try:
                record = (
                    MailingRecord.objects.select_for_update()
                    .get(pk=mailing_id, status=MailingStatus.PENDING)
                )
            except MailingRecord.DoesNotExist:
                # Already delivered or does not exist — nothing to do.
                logger.warning(
                    "dispatch_mailing: record %d not found or not PENDING", mailing_id
                )
                return

            record.status = MailingStatus.SENDING
            record.save(update_fields=["status", "updated_at"])

        send_email(
            recipient=record.email,
            subject=record.subject,
            message=record.message,
            user_id=record.user_id,
            external_id=record.external_id,
        )

        record.status = MailingStatus.SENT
        record.error  = ""
        record.save(update_fields=["status", "error", "updated_at"])

    except Exception as exc:
        logger.exception("dispatch_mailing: unexpected error for record %d", mailing_id)
        MailingRecord.objects.filter(pk=mailing_id).update(
            status=MailingStatus.FAILED,
            error=str(exc),
        )
