import threading
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_in_background(fn, *args, **kwargs):
    """Run an email-sending function in a background thread."""
    thread = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    thread.start()


def send_submission_confirmation(submission, request=None):
    """Send confirmation email to author and co-authors after paper submission."""
    conference = submission.membership.conference
    author = submission.membership.user

    authors = [author]
    for co_author in [submission.co_author1, submission.co_author2, submission.co_author3]:
        if co_author:
            authors.append(co_author)

    base_url = request.build_absolute_uri('/') if request else ''
    submission_url = f"{base_url}submissions/{submission.pk}/"
    conference_url = f"{base_url}conference/{conference.slug}/"

    context = {
        'conference': conference,
        'submission': submission,
        'authors': authors,
        'submission_date': timezone.now().strftime('%B %d, %Y'),
        'submission_url': submission_url,
        'conference_url': conference_url,
    }

    html_message = render_to_string('submissions/emails/submission_confirmation.html', context)
    recipients = [a.email for a in authors]

    def _send():
        try:
            send_mail(
                subject=f"Submission Confirmation: {submission.paper_title}",
                message=f"Your paper '{submission.paper_title}' has been submitted to {conference.conference_name}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
            )
        except Exception as e:
            logger.error(f"Failed to send submission confirmation email: {e}")

    _send_in_background(_send)


def send_reviewer_assignment(review, request=None):
    """Send notification to reviewer when assigned to a paper."""
    submission = review.submission
    conference = submission.membership.conference
    reviewer = review.reviewer

    base_url = request.build_absolute_uri('/') if request else ''
    review_url = f"{base_url}review/submit/{review.pk}/"
    submission_url = f"{base_url}submissions/{submission.pk}/"
    conference_url = f"{base_url}conference/{conference.slug}/"

    context = {
        'conference': conference,
        'submission': submission,
        'reviewer': reviewer,
        'assignment_date': timezone.now().strftime('%B %d, %Y'),
        'review_url': review_url,
        'submission_url': submission_url,
        'conference_url': conference_url,
    }

    html_message = render_to_string('submissions/emails/reviewer_assignment.html', context)

    def _send():
        try:
            send_mail(
                subject=f"Review Assignment: {submission.paper_title}",
                message=f"You have been assigned to review '{submission.paper_title}' for {conference.conference_name}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reviewer.email],
                html_message=html_message,
            )
        except Exception as e:
            logger.error(f"Failed to send reviewer assignment email: {e}")

    _send_in_background(_send)


def send_review_notification(review, request=None):
    """Send notification to author when a review is submitted."""
    submission = review.submission
    conference = submission.membership.conference
    author = submission.membership.user

    base_url = request.build_absolute_uri('/') if request else ''
    submission_url = f"{base_url}submissions/{submission.pk}/"
    conference_url = f"{base_url}conference/{conference.slug}/"

    context = {
        'conference': conference,
        'submission': submission,
        'review': review,
        'reviewer': review.reviewer,
        'review_date': timezone.now().strftime('%B %d, %Y'),
        'submission_url': submission_url,
        'conference_url': conference_url,
    }

    html_message = render_to_string('submissions/emails/review_notification.html', context)

    recipients = [author.email]
    for co_author in [submission.co_author1, submission.co_author2, submission.co_author3]:
        if co_author:
            recipients.append(co_author.email)

    def _send():
        try:
            send_mail(
                subject=f"Review Received: {submission.paper_title}",
                message=f"A review has been submitted for your paper '{submission.paper_title}'.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
            )
        except Exception as e:
            logger.error(f"Failed to send review notification email: {e}")

    _send_in_background(_send)


def send_submission_decision(submission):
    """Send accept/reject/revision notification to authors when status changes."""
    conference = submission.membership.conference
    author = submission.membership.user

    decision = submission.status
    if decision not in ('ACCEPTED', 'REJECTED', 'REVISION'):
        return

    decision_display = submission.get_status_display()
    header_colors = {
        'ACCEPTED': '#28a745',
        'REJECTED': '#dc3545',
        'REVISION': '#f59e0b',
    }
    header_color = header_colors.get(decision, '#667eea')

    context = {
        'conference': conference,
        'submission': submission,
        'author_name': author.get_full_name(),
        'decision': decision,
        'decision_display': decision_display,
        'header_color': header_color,
        'submission_url': f'/submissions/{submission.pk}/',
    }

    html_message = render_to_string('submissions/emails/submission_decision.html', context)

    recipients = [author.email]
    for co_author in [submission.co_author1, submission.co_author2, submission.co_author3]:
        if co_author:
            recipients.append(co_author.email)

    def _send():
        try:
            send_mail(
                subject=f"Paper {decision_display}: {submission.paper_title}",
                message=f"Your paper '{submission.paper_title}' has been {decision_display.lower()} for {conference.conference_name}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
            )
        except Exception as e:
            logger.error(f"Failed to send submission decision email: {e}")

    _send_in_background(_send)


def send_registration_confirmation(user, conference, membership, request=None):
    """Send HTML confirmation email with attached invoice PDF after payment."""
    from conference.models import Payment

    payment = Payment.objects.filter(
        user=user, conference=conference, status='completed'
    ).order_by('-created_at').first()

    base_url = request.build_absolute_uri('/') if request else ''
    dashboard_url = f"{base_url}conference/dashboard/"
    conference_url = f"{base_url}conference/{conference.slug}/"

    context = {
        'user': user,
        'conference': conference,
        'membership': membership,
        'payment': payment,
        'registration_date': timezone.now().strftime('%B %d, %Y'),
        'dashboard_url': dashboard_url,
        'conference_url': conference_url,
        'has_invoice': payment is not None,
    }

    html_message = render_to_string('submissions/emails/registration_confirmation.html', context)
    plain_message = (
        f"Dear {user.get_full_name()},\n\n"
        f"Your registration for {conference.conference_name} has been confirmed.\n"
        f"Role: {membership.role1}"
        f"{', ' + membership.role2 if membership.role2 != 'N/A' else ''}\n"
    )
    if payment:
        plain_message += f"Amount Paid: ${payment.amount} {payment.currency}\n"
        plain_message += f"Invoice: INV-{payment.id:06d}\n"
    plain_message += f"\nThank you for registering!\n\nIATM Conference Management System"

    # Pre-generate invoice PDF in the main thread (needs DB access)
    invoice_data = None
    if payment:
        try:
            from conference.invoice import generate_invoice_pdf
            invoice_buffer = generate_invoice_pdf(payment)
            invoice_data = (
                f"IATM_Invoice_{payment.id:06d}.pdf",
                invoice_buffer.getvalue(),
                'application/pdf',
            )
        except Exception as e:
            logger.error(f"Failed to generate invoice PDF: {e}")

    def _send():
        try:
            email = EmailMultiAlternatives(
                subject=f"Registration Confirmed: {conference.conference_name}",
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_message, "text/html")

            if invoice_data:
                email.attach(*invoice_data)

            email.send()
        except Exception as e:
            logger.error(f"Failed to send registration confirmation email: {e}")

    _send_in_background(_send)
