import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator
from conference.models import Conference, Payment
from .models import Membership, Role
from .forms import MembershipForm
from django.contrib.admin.views.decorators import staff_member_required


@login_required
def networking_hub(request, slug):
    """Attendee directory for networking (paid registrants only)."""
    conference = get_object_or_404(Conference, slug=slug)

    # Only paid registrants can access
    if not Membership.objects.filter(user=request.user, conference=conference, is_paid=True).exists():
        messages.error(request, "You must be a paid registrant to access the networking hub.")
        return redirect('conference_detail', slug=slug)

    attendees = Membership.objects.filter(conference=conference, is_paid=True).select_related('user').order_by('user__last_name', 'user__first_name')

    query = request.GET.get('q', '')
    if query:
        attendees = attendees.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__organization__icontains=query) |
            Q(user__country__icontains=query)
        )

    paginator = Paginator(attendees, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'conference': conference,
        'attendees': page_obj,
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'membership/networking_hub.html', context)


@login_required
def group_registration(request, slug):
    """Register and pay for multiple attendees at once."""
    conference = get_object_or_404(Conference, slug=slug)
    from conference.models import RegistrationTier

    tiers = RegistrationTier.objects.filter(conference=conference, is_active=True)
    is_member = request.user.iatm_membership

    if request.method == 'POST':
        action = request.POST.get('action', 'register')

        if action == 'register':
            # Step 1: Register attendees (create unpaid memberships)
            emails_raw = request.POST.get('emails', '')
            emails = [e.strip() for e in emails_raw.split('\n') if e.strip()]

            if not emails:
                messages.error(request, "Please enter at least one email address.")
                return redirect('group_registration', slug=slug)

            from accounts.models import CustomUser
            registered = []
            errors = []

            for email in emails:
                try:
                    user = CustomUser.objects.get(email=email)
                    if Membership.objects.filter(user=user, conference=conference).exists():
                        errors.append(f"{email} is already registered.")
                    else:
                        Membership.objects.create(
                            user=user,
                            conference=conference,
                            role1='Author',
                            is_paid=False,
                        )
                        registered.append(email)
                except CustomUser.DoesNotExist:
                    errors.append(f"{email} - no account found.")

            if registered:
                messages.success(request, f"Registered {len(registered)} attendee(s): {', '.join(registered)}")
            if errors:
                messages.warning(request, "Issues: " + "; ".join(errors))

            return redirect('group_registration', slug=slug)

        elif action == 'pay':
            # Step 2: Pay for selected unpaid members
            member_ids = request.POST.getlist('member_ids')
            tier_id = request.POST.get('tier_id')

            if not member_ids:
                messages.error(request, "Please select at least one attendee to pay for.")
                return redirect('group_registration', slug=slug)

            unpaid = Membership.objects.filter(
                id__in=member_ids, conference=conference, is_paid=False
            )
            count = unpaid.count()
            if count == 0:
                messages.info(request, "All selected attendees are already paid.")
                return redirect('group_registration', slug=slug)

            # Calculate total amount
            if tier_id and tiers.exists():
                tier = get_object_or_404(RegistrationTier, id=tier_id, conference=conference)
                unit_price = tier.get_current_price(is_member=is_member)
                tier_name = tier.name
            else:
                tier = None
                unit_price = 50.00 if request.user.occupation in ['student_undergraduate', 'student_graduate'] else 100.00
                tier_name = "Registration"

            total_amount = round(unit_price * count, 2)

            # Create pending payment record
            payment = Payment.objects.create(
                user=request.user,
                conference=conference,
                tier=tier,
                amount=total_amount,
                status='pending'
            )

            # Store group info in session for post-payment processing
            request.session['group_payment_id'] = payment.id
            request.session['group_member_ids'] = list(unpaid.values_list('id', flat=True))
            request.session['group_conference_slug'] = slug

            # Redirect to PayPal NCP payment link
            paypal_link = settings.PAYPAL_PAYMENT_LINK
            return redirect(paypal_link)

    # GET: show form with unpaid members and tier selection
    memberships = Membership.objects.filter(conference=conference).select_related('user').order_by('-created_at')[:20]
    unpaid_memberships = Membership.objects.filter(conference=conference, is_paid=False).select_related('user')

    # Build tier pricing for display
    tier_pricing = []
    for tier in tiers:
        current_price = tier.get_current_price(is_member=is_member)
        tier_pricing.append({
            'tier': tier,
            'price': current_price,
        })

    context = {
        'conference': conference,
        'tiers': tiers,
        'tier_pricing': tier_pricing,
        'recent_memberships': memberships,
        'unpaid_memberships': unpaid_memberships,
        'is_member': is_member,
        'is_early_bird': conference.is_early_bird,
    }
    return render(request, 'membership/group_registration.html', context)


@login_required
def group_payment_success(request, slug):
    """Handle return from PayPal for group registration."""
    conference = get_object_or_404(Conference, slug=slug)

    group_payment_id = request.session.get('group_payment_id')
    member_ids = request.session.get('group_member_ids', [])
    conf_slug = request.session.get('group_conference_slug')

    if not group_payment_id or conf_slug != slug:
        messages.error(request, "Invalid payment session.")
        return redirect('group_registration', slug=slug)

    try:
        payment = Payment.objects.get(id=group_payment_id, user=request.user)
        if payment.status == 'pending':
            payment.status = 'completed'
            payment.save()

            # Mark all group members as paid
            paid_count = Membership.objects.filter(
                id__in=member_ids, conference=conference
            ).update(is_paid=True)

            messages.success(
                request,
                f"Group payment confirmed! {paid_count} attendee(s) are now registered."
            )
    except Payment.DoesNotExist:
        messages.error(request, "Payment record not found.")

    # Clear session
    for key in ['group_payment_id', 'group_member_ids', 'group_conference_slug']:
        request.session.pop(key, None)

    return redirect('group_registration', slug=slug)


@login_required
def register_for_conference(request, slug):
    conference = get_object_or_404(Conference, slug=slug)

    # Check existing membership
    if Membership.objects.filter(user=request.user, conference=conference).exists():
        messages.info(request, "You have already registered for this conference.")
        return redirect('conference_detail', slug=slug)

    if request.method == 'POST':
        form = MembershipForm(request.POST)
        if form.is_valid():
            Membership.objects.create(
                user=request.user,
                conference=conference,
                role1=form.cleaned_data['role1'],
                role2=form.cleaned_data['role2']
            )
            messages.success(request, "Registration submitted successfully!")
            return redirect('conference_detail', slug=slug)
    else:
        form = MembershipForm()

    return render(request, 'membership/register.html', {
        'conference': conference,
        'form': form
    })


@staff_member_required
def admin_conference_dashboard_view(request, slug):
    conference = get_object_or_404(Conference, slug=slug)
    memberships = Membership.objects.filter(conference=conference).select_related('user').exclude(user__is_staff=True)

    if request.method == 'POST':
        action = request.POST.get('action', 'update_roles')
        member_id = request.POST.get('membership_id')
        membership = Membership.objects.get(id=member_id)

        if action == 'toggle_payment':
            membership.is_paid = not membership.is_paid
            membership.save()
            status = "paid" if membership.is_paid else "unpaid"
            messages.success(request, f"{membership.user.get_full_name()} marked as {status}.")
        else:
            role1 = request.POST.get('role1')
            role2 = request.POST.get('role2')
            membership.role1 = role1
            membership.role2 = role2
            membership.save()

        return redirect('admin_conference_dashboard', slug=slug)

    return render(request, 'conference/admin_dashboard.html', {
        'conference': conference,
        'memberships': memberships,
        'Role': Role,
    })


@staff_member_required
def admin_analytics_view(request, slug):
    """Real-time analytics: revenue, registrations, geography."""
    conference = get_object_or_404(Conference, slug=slug)
    memberships = Membership.objects.filter(conference=conference)

    # Registration stats
    total_registrations = memberships.count()
    paid_registrations = memberships.filter(is_paid=True).count()
    unpaid_registrations = total_registrations - paid_registrations

    # Revenue
    payments = Payment.objects.filter(conference=conference, status='completed')
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0

    # Role breakdown
    authors = memberships.filter(Q(role1='Author') | Q(role2='Author')).count()
    reviewers = memberships.filter(Q(role1='Reviewer') | Q(role2='Reviewer')).count()
    chairs = memberships.filter(Q(role1='Chair') | Q(role2='Chair')).count()

    # Geography (country breakdown)
    country_stats = memberships.values('user__country').annotate(
        count=Count('id')
    ).order_by('-count')[:15]

    # Occupation breakdown
    occupation_stats = memberships.values('user__occupation').annotate(
        count=Count('id')
    ).order_by('-count')

    context = {
        'conference': conference,
        'total_registrations': total_registrations,
        'paid_registrations': paid_registrations,
        'unpaid_registrations': unpaid_registrations,
        'total_revenue': total_revenue,
        'authors': authors,
        'reviewers': reviewers,
        'chairs': chairs,
        'country_stats': country_stats,
        'occupation_stats': occupation_stats,
        'country_labels': json.dumps([str(c['user__country'] or 'Unknown') for c in country_stats]),
        'country_data': json.dumps([c['count'] for c in country_stats]),
        'occupation_labels': json.dumps([str(o['user__occupation'] or 'Unknown') for o in occupation_stats]),
        'occupation_data': json.dumps([o['count'] for o in occupation_stats]),
    }
    return render(request, 'membership/admin_analytics.html', context)


@staff_member_required
def export_attendees_csv(request, slug):
    """Export attendee list as CSV."""
    conference = get_object_or_404(Conference, slug=slug)
    memberships = Membership.objects.filter(conference=conference).select_related('user')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{conference.slug}_attendees.csv"'

    writer = csv.writer(response)
    writer.writerow(['Email', 'First Name', 'Last Name', 'Organization', 'Country', 'Phone', 'Occupation', 'Role 1', 'Role 2', 'Paid', 'Registration Date'])

    for m in memberships:
        writer.writerow([
            m.user.email,
            m.user.first_name,
            m.user.last_name,
            m.user.organization,
            m.user.country,
            m.user.phone,
            m.user.get_occupation_display(),
            m.role1,
            m.role2,
            'Yes' if m.is_paid else 'No',
            m.created_at.strftime('%Y-%m-%d'),
        ])

    return response


@staff_member_required
def export_financials_csv(request, slug):
    """Export financial report as CSV."""
    conference = get_object_or_404(Conference, slug=slug)
    payments = Payment.objects.filter(conference=conference).select_related('user', 'tier')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{conference.slug}_financials.csv"'

    writer = csv.writer(response)
    writer.writerow(['Invoice #', 'Email', 'Name', 'Tier', 'Amount', 'Currency', 'Status', 'PayPal Order ID', 'Date'])

    for p in payments:
        writer.writerow([
            f'INV-{p.id:06d}',
            p.user.email,
            p.user.get_full_name(),
            p.tier.name if p.tier else 'N/A',
            p.amount,
            p.currency,
            p.get_status_display(),
            p.paypal_order_id or '',
            p.created_at.strftime('%Y-%m-%d'),
        ])

    return response


@login_required
def download_badge(request, membership_id):
    """Download printable name badge PDF with QR code."""
    membership = get_object_or_404(Membership, id=membership_id)

    if membership.user != request.user and not request.user.is_staff:
        messages.error(request, "You are not authorized to download this badge.")
        return redirect('user_dashboard')

    if not membership.is_paid:
        messages.error(request, "Badge is only available for paid registrations.")
        return redirect('user_dashboard')

    from .badge import generate_badge_pdf
    buffer = generate_badge_pdf(membership)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="badge_{membership.user.first_name}_{membership.conference.slug}.pdf"'
    return response


@login_required
def download_qr_ticket(request, membership_id):
    """Download QR code ticket as PNG image."""
    membership = get_object_or_404(Membership, id=membership_id)

    if membership.user != request.user and not request.user.is_staff:
        messages.error(request, "Not authorized.")
        return redirect('user_dashboard')

    if not membership.is_paid:
        messages.error(request, "QR ticket is only available for paid registrations.")
        return redirect('user_dashboard')

    from .badge import generate_qr_code
    qr_data = f"IATM|{membership.user.email}|{membership.conference.slug}|{membership.id}"
    qr_buf = generate_qr_code(qr_data)

    response = HttpResponse(qr_buf.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="ticket_{membership.conference.slug}.png"'
    return response


@staff_member_required
def bulk_email_view(request, slug):
    """Send bulk HTML emails to segmented attendee lists."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    conference = get_object_or_404(Conference, slug=slug)
    memberships = Membership.objects.filter(conference=conference).select_related('user')

    if request.method == 'POST':
        subject = request.POST.get('subject', '')
        body = request.POST.get('body', '')
        segment = request.POST.get('segment', 'all')

        if not subject or not body:
            messages.error(request, "Subject and body are required.")
            return redirect('bulk_email', slug=slug)

        # Segment recipients
        recipients = memberships
        if segment == 'paid':
            recipients = recipients.filter(is_paid=True)
        elif segment == 'unpaid':
            recipients = recipients.filter(is_paid=False)
        elif segment == 'authors':
            recipients = recipients.filter(Q(role1='Author') | Q(role2='Author'))
        elif segment == 'reviewers':
            recipients = recipients.filter(Q(role1='Reviewer') | Q(role2='Reviewer'))

        # Render HTML email using branded template
        html_message = render_to_string('submissions/emails/bulk_email.html', {
            'subject': subject,
            'body': body,
            'conference': conference,
        })

        sent_count = 0
        fail_count = 0
        for m in recipients:
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[m.user.email],
                )
                email.attach_alternative(html_message, "text/html")
                email.send()
                sent_count += 1
            except Exception:
                fail_count += 1

        if sent_count:
            messages.success(request, f"HTML email sent to {sent_count} recipient(s).")
        if fail_count:
            messages.warning(request, f"Failed to send to {fail_count} recipient(s).")
        if not sent_count and not fail_count:
            messages.warning(request, "No recipients matched the selected segment.")

        return redirect('bulk_email', slug=slug)

    segment_counts = {
        'all': memberships.count(),
        'paid': memberships.filter(is_paid=True).count(),
        'unpaid': memberships.filter(is_paid=False).count(),
        'authors': memberships.filter(Q(role1='Author') | Q(role2='Author')).count(),
        'reviewers': memberships.filter(Q(role1='Reviewer') | Q(role2='Reviewer')).count(),
    }

    context = {
        'conference': conference,
        'segment_counts': segment_counts,
    }
    return render(request, 'membership/bulk_email.html', context)


@login_required
def message_inbox(request):
    """Inbox showing received messages across all conferences."""
    from .models import AttendeeMessage

    received = AttendeeMessage.objects.filter(recipient=request.user).select_related(
        'sender', 'conference'
    )
    sent = AttendeeMessage.objects.filter(sender=request.user).select_related(
        'recipient', 'conference'
    )

    tab = request.GET.get('tab', 'inbox')
    unread_count = received.filter(is_read=False).count()

    context = {
        'received_messages': received,
        'sent_messages': sent,
        'tab': tab,
        'unread_count': unread_count,
    }
    return render(request, 'membership/message_inbox.html', context)


@login_required
def message_detail(request, message_id):
    """View a single message and mark as read."""
    from .models import AttendeeMessage

    msg = get_object_or_404(AttendeeMessage, id=message_id)

    # Only sender or recipient can view
    if msg.sender != request.user and msg.recipient != request.user:
        messages.error(request, "You are not authorized to view this message.")
        return redirect('message_inbox')

    # Mark as read if recipient is viewing
    if msg.recipient == request.user and not msg.is_read:
        msg.is_read = True
        msg.save()

    # Get conversation thread (messages between these two users for this conference)
    thread = AttendeeMessage.objects.filter(
        conference=msg.conference,
    ).filter(
        Q(sender=msg.sender, recipient=msg.recipient) |
        Q(sender=msg.recipient, recipient=msg.sender)
    ).select_related('sender', 'recipient').order_by('created_at')

    context = {
        'message': msg,
        'thread': thread,
    }
    return render(request, 'membership/message_detail.html', context)


@login_required
def send_message(request, slug, recipient_id):
    """Send a message to another attendee within a conference."""
    from .models import AttendeeMessage
    from accounts.models import CustomUser

    conference = get_object_or_404(Conference, slug=slug)
    recipient = get_object_or_404(CustomUser, id=recipient_id)

    # Verify both sender and recipient are paid members of this conference
    sender_member = Membership.objects.filter(
        user=request.user, conference=conference, is_paid=True
    ).first()
    recipient_member = Membership.objects.filter(
        user=recipient, conference=conference, is_paid=True, messaging_opt_in=True
    ).first()

    if not sender_member:
        messages.error(request, "You must be a paid registrant to send messages.")
        return redirect('networking_hub', slug=slug)

    if not recipient_member:
        messages.error(request, "This attendee is not available for messaging.")
        return redirect('networking_hub', slug=slug)

    if request.user == recipient:
        messages.error(request, "You cannot send a message to yourself.")
        return redirect('networking_hub', slug=slug)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()

        if not subject or not body:
            messages.error(request, "Subject and message are required.")
        else:
            AttendeeMessage.objects.create(
                conference=conference,
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
            )
            messages.success(request, f"Message sent to {recipient.get_full_name()}.")
            return redirect('networking_hub', slug=slug)

    context = {
        'conference': conference,
        'recipient': recipient,
    }
    return render(request, 'membership/send_message.html', context)
