from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from .forms import SubmissionForm
from .models import Submissions
from conference.models import Conference
from membership.models import Membership, Role
from review.models import Review
from .decorators import require_paid_membership
from .emails import send_submission_confirmation
from django.shortcuts import get_object_or_404
import os


@login_required
@require_paid_membership
def create_submission(request, slug):
    conference = get_object_or_404(Conference, slug=slug)

    # Roles for sidebar - match context processors
    is_chair = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Chair') | Q(role2='Chair')
    ).exists()
    is_reviewer = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Reviewer') | Q(role2='Reviewer')
    ).exists()

    if not Membership.objects.filter(user=request.user, conference=conference).exists():
        messages.error(request, "You are not a member of this conference to submit a paper")
        return redirect('conference_detail', slug=slug)

    if not conference.is_submission_open:
        messages.error(request, "The submission deadline has passed for this conference.")
        return redirect('conference_detail', slug=slug)

    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES, conference=conference)
        if form.is_valid():
            submission = form.save(commit=False)
            membership = Membership.objects.get(user=request.user, conference=conference)
            submission.membership = membership
            submission.save()
            send_submission_confirmation(submission, request)
            messages.success(request, "Submission Successfully Submitted")
            return redirect('submission_detail', pk=submission.pk)
        else:
            messages.error(request, "Please correct the errors below")
    else:
        form = SubmissionForm(conference=conference)

    return render(request, 'submissions/create_submissions.html', {
        'conference': conference,
        'form': form,
        'is_chair': is_chair,
        'is_reviewer': is_reviewer,
    })


@login_required
def submission_detail(request, pk):
    submission = get_object_or_404(Submissions, pk=pk)

    # Roles for sidebar - match context processors
    is_chair = request.user.is_staff or Membership.objects.filter(
        user=request.user,
        conference=submission.membership.conference
    ).filter(
        Q(role1='Chair') | Q(role2='Chair')
    ).exists()
    is_reviewer = request.user.is_staff or Membership.objects.filter(
        user=request.user,
        conference=submission.membership.conference
    ).filter(
        Q(role1='Reviewer') | Q(role2='Reviewer')
    ).exists()

    is_authorized = (
        is_chair or
        submission.membership.user == request.user or
        request.user in [submission.co_author1, submission.co_author2, submission.co_author3]
    )

    if not is_authorized:
        messages.error(request, "You are not authorized to view this submission")
        return redirect('conference_detail', slug=submission.membership.conference.slug)

    reviews = Review.objects.filter(submission=submission).order_by('-date_reviewed')

    return render(request, 'submissions/submission_detail.html', {
        'submission': submission,
        'conference': submission.membership.conference,
        'reviews': reviews,
        'is_chair': is_chair,
        'is_reviewer': is_reviewer,
    })


@login_required
def submission_list(request):
    # Roles for sidebar - match context processors
    is_chair = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Chair') | Q(role2='Chair')
    ).exists()
    is_reviewer = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Reviewer') | Q(role2='Reviewer')
    ).exists()

    chair_conferences = Membership.objects.filter(
        user=request.user,
        role1='Chair'
    ).values_list('conference', flat=True)

    if chair_conferences:
        all_submissions = Submissions.objects.filter(
            membership__conference__in=chair_conferences
        ).order_by('-submission_date')
    else:
        all_submissions = Submissions.objects.filter(
            membership__user=request.user
        ).order_by('-submission_date')

        co_authored_submissions = Submissions.objects.filter(
            Q(co_author1=request.user) |
            Q(co_author2=request.user) |
            Q(co_author3=request.user)
        ).order_by('-submission_date')

        all_submissions = (all_submissions | co_authored_submissions).distinct()

    paginator = Paginator(all_submissions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    for submission in page_obj:
        is_co_author = request.user in [submission.co_author1, submission.co_author2, submission.co_author3]
        submission.is_co_author = is_co_author

        roles = set()
        if submission.membership.user == request.user:
            roles.add("Author")
        elif is_co_author:
            roles.add("Co-Author")
        else:
            roles.add("Viewer")

        if submission.membership.role1 != 'N/A':
            roles.add(submission.membership.get_role1_display())
        if submission.membership.role2 != 'N/A':
            roles.add(submission.membership.get_role2_display())

        submission.roles = sorted(list(roles))

    return render(request, 'submissions/submission_list.html', {
        'all_submissions': page_obj,
        'page_obj': page_obj,
        'is_chair': is_chair,
        'is_reviewer': is_reviewer,
        'user': request.user,
    })


@login_required
def edit_submission(request, pk):
    # Roles for sidebar - match context processors
    is_chair = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Chair') | Q(role2='Chair')
    ).exists()
    is_reviewer = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Reviewer') | Q(role2='Reviewer')
    ).exists()

    submission = get_object_or_404(Submissions, pk=pk)

    # Authorization check
    if submission.membership.user != request.user and request.user not in [
        submission.co_author1, submission.co_author2, submission.co_author3
    ]:
        messages.error(request, "You are not authorized to edit this submission")
        return redirect('submission_detail', pk=pk)

    # Status check
    if submission.status in ['ACCEPTED', 'REJECTED']:
        messages.error(request, "Cannot edit submission after it has been accepted or rejected")
        return redirect('submission_detail', pk=pk)

    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES, instance=submission, conference=submission.membership.conference)
        if form.is_valid():
            form.save()
            messages.success(request, "Submission successfully updated")
            return redirect('submission_detail', pk=pk)
        else:
            messages.error(request, "Please correct the errors below")
            print("FORM ERRORS:", form.errors.as_data())
    else:
        initial_data = {
            'co_author_email_1': submission.co_author1.email if submission.co_author1 else '',
            'co_author_email_2': submission.co_author2.email if submission.co_author2 else '',
            'co_author_email_3': submission.co_author3.email if submission.co_author3 else ''
        }
        form = SubmissionForm(instance=submission, initial=initial_data, conference=submission.membership.conference)

    return render(request, 'submissions/edit_submission.html', {
        'form': form,
        'submission': submission,
        'conference': submission.membership.conference,
        'is_chair': is_chair,
        'is_reviewer': is_reviewer,
    })


@login_required
def delete_submission(request, pk):
    # Roles for sidebar - match context processors
    is_chair = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Chair') | Q(role2='Chair')
    ).exists()
    is_reviewer = request.user.is_staff or Membership.objects.filter(
        user=request.user
    ).filter(
        Q(role1='Reviewer') | Q(role2='Reviewer')
    ).exists()

    submission = get_object_or_404(Submissions, pk=pk)

    if submission.membership.user != request.user and request.user not in [
        submission.co_author1, submission.co_author2, submission.co_author3
    ]:
        messages.error(request, "You are not authorized to delete this submission")
        return redirect('submission_detail', pk=pk)

    if submission.status == 'ACCEPTED':
        messages.error(request, "Cannot delete an accepted submission")
        return redirect('submission_detail', pk=pk)

    if request.method == 'POST':
        conference_slug = submission.membership.conference.slug

        if submission.file and os.path.isfile(submission.file.path):
            os.remove(submission.file.path)

        submission.delete()
        messages.success(request, "Submission successfully deleted")
        return redirect('conference_detail', slug=conference_slug)

    return render(request, 'submissions/delete_confirmation.html', {
        'submission': submission,
        'conference': submission.membership.conference,
        'is_chair': is_chair,
        'is_reviewer': is_reviewer,
    })


def proceedings_list(request):
    """List all conferences with accepted papers (digital proceedings)."""
    conferences = Conference.objects.filter(
        memberships__submissions__status='ACCEPTED'
    ).distinct()

    context = {'conferences': conferences}
    return render(request, 'submissions/proceedings_list.html', context)


def proceedings_conference(request, slug):
    """Searchable archive of accepted papers for a conference."""
    conference = get_object_or_404(Conference, slug=slug)
    papers = Submissions.objects.filter(
        membership__conference=conference,
        status='ACCEPTED'
    ).select_related('membership__user', 'track')

    # Search filter
    query = request.GET.get('q', '')
    if query:
        papers = papers.filter(
            Q(paper_title__icontains=query) |
            Q(membership__user__first_name__icontains=query) |
            Q(membership__user__last_name__icontains=query)
        )

    track_filter = request.GET.get('track')
    if track_filter:
        papers = papers.filter(track__id=track_filter)

    tracks = conference.tracks.all()

    context = {
        'conference': conference,
        'papers': papers,
        'tracks': tracks,
        'query': query,
        'track_filter': track_filter,
    }
    return render(request, 'submissions/proceedings_conference.html', context)
