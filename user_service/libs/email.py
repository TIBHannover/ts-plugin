import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string

from user.models import EmailLog, RoleModel
from user.tasks import send_notification_email


logger = logging.getLogger(__name__)


class Email:
    def __init__(self, subject, body, client_ts="", html_body=None, unfollow_links=()):
        self.subject = subject
        self.body = body
        self.html_body = html_body
        self.sender_email = settings.DEFAULT_FROM_EMAIL
        self.client_ts = client_ts
        self.unfollow_links = unfollow_links

    def send(self, recipients, notification_type="general", reference="", is_admin=False):
        base = getattr(settings, f"{self.client_ts.upper()}_FRONTEND_REDIRECT_URL", None)
        footer_links = [
            (label, urljoin(base.rstrip("/") + "/", path))
            for label, path in (("Contact", "contact"), ("Documentation", "docs"), ("Terms of Use", "TermsOfUse"))
        ] if base else []
        service_description = (
            "The Terminology Service provides a central access point to current ontologies and "
            "scientific vocabularies. Search and browse ontology terms, definitions, and relationships "
            "through the website, or retrieve terminology through the API to integrate it into "
            "research tools and data repositories. The service supports consistent, machine-readable "
            "descriptions of research data and helps make it FAIR: findable, accessible, interoperable, "
            "and reusable."
        )
        html_body = render_to_string("notification/email.html", {
            "subject": self.subject, "body": self.body, "html_body": self.html_body,
            "service_description": service_description, "footer_links": footer_links,
            "is_admin": is_admin,
            "unfollow_links": self.unfollow_links,
        })
        body = (
            ("FOR SYSTEM ADMINS\n\n" if is_admin else "") + self.body
            + "".join(f"\n\nUnfollow {ontology_id}: {url}" for ontology_id, url in self.unfollow_links)
            + f"\n\nAbout the Terminology Service\n{service_description}\n"
            + "".join(f"\n{label}: {url}" for label, url in footer_links)
        )
        logs = []
        for recipient in dict.fromkeys(recipients):
            email_log = EmailLog.objects.create(
                notification_type=notification_type,
                reference=reference,
                client_ts=self.client_ts,
                recipient=recipient,
                sender=self.sender_email,
                subject=self.subject,
            )
            logs.append(email_log)

            def enqueue(email_log_id=email_log.pk):
                try:
                    send_notification_email.delay(email_log_id, body, html_body)
                except Exception as exc:
                    EmailLog.objects.filter(pk=email_log_id).update(
                        status=EmailLog.Status.FAILED, last_error=str(exc)
                    )
                    logger.exception("Could not queue notification %s", email_log_id)

            transaction.on_commit(enqueue)
        return logs

    def report_content_to_admins(self, reference=""):
        self.send(
            RoleModel(client_ts=self.client_ts).get_system_admin_emails(),
            notification_type="content_report",
            reference=reference,
            is_admin=True,
        )
        return True
