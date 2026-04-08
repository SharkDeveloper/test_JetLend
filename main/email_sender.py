"""
Email sending abstraction.

In production this module would delegate to Django's email backend
(django.core.mail.send_mail).  For this assignment, sending is simulated by
sleeping a random amount of time and writing to the application log, exactly
as specified in the task description.
"""

import logging
import time
from random import randint

logger = logging.getLogger(__name__)


def send_email(
    *,
    recipient: str,
    subject: str,
    message: str,
    user_id: int,
    external_id: str,
) -> None:
    """
    Simulate sending an email.

    Sleeps for a random interval (5–20 s) to model real SMTP latency,
    then logs the message at INFO level.

    Parameters
    ----------
    recipient:   Email address of the recipient.
    subject:     Email subject line.
    message:     Plain-text body of the email.
    user_id:     ID of the target user in our system.
    external_id: Idempotency key from the external system.
    """
    delay = randint(5, 20)
    logger.debug(
        "Simulating SMTP delivery (sleeping %ds) for external_id=%s",
        delay,
        external_id,
    )
    time.sleep(delay)

    logger.info(
        "Send EMAIL | external_id=%s user_id=%d to=%s subject=%r",
        external_id,
        user_id,
        recipient,
        subject,
    )
