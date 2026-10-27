"""
Delivery adapters.

The alerts module says "send this message to this person". It does not
know Beem exists. Swap the driver, nothing else moves.

SMS_BACKEND=log everywhere except production, so nobody is woken at 3am
by a test run.
"""

import logging

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger("alerts")


class SmsBackend:
    def send(self, phone, message):
        raise NotImplementedError


class LogSmsBackend(SmsBackend):
    def send(self, phone, message):
        logger.info("[SMS:log] to=%s body=%r", phone, message)
        return True


class BeemSmsBackend(SmsBackend):
    """
    Beem Africa.

    Verify the payload shape against Beem's current docs before going
    live -- auth format and field names are exactly the sort of thing
    that changes. The structure here (adapter behind an interface) holds
    regardless of what their JSON looks like.
    """

    def send(self, phone, message):
        if not (settings.BEEM_API_KEY and settings.BEEM_SECRET_KEY):
            logger.error("Beem credentials missing; refusing to send.")
            return False

        payload = {
            "source_addr": settings.BEEM_SENDER_ID,
            "encoding": 0,
            "message": message,
            "recipients": [{"recipient_id": 1, "dest_addr": phone}],
        }
        try:
            response = requests.post(
                settings.BEEM_SEND_URL,
                json=payload,
                auth=(settings.BEEM_API_KEY, settings.BEEM_SECRET_KEY),
                timeout=15,
            )
            response.raise_for_status()
            logger.info("[SMS:beem] to=%s ok", phone)
            return True
        except requests.RequestException as exc:
            logger.error("[SMS:beem] to=%s failed: %s", phone, exc)
            return False


def get_sms_backend():
    if settings.SMS_BACKEND == "beem":
        return BeemSmsBackend()
    return LogSmsBackend()


def send_sms(phone, message):
    if not phone:
        return False
    return get_sms_backend().send(phone, message)


def send_email(to_email, subject, text_body, html_body=None):
    if not to_email:
        return False
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True
