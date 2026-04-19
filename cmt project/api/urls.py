from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ConferenceViewSet,
    TrackViewSet,
    RegistrationTierViewSet,
    MembershipViewSet,
    SubmissionViewSet,
    ReviewViewSet,
    SessionViewSet,
    SpeakerViewSet,
    PaymentViewSet,
    UserProfileView,
)

router = DefaultRouter()
router.register(r'conferences', ConferenceViewSet, basename='conference')
router.register(r'tracks', TrackViewSet, basename='track')
router.register(r'tiers', RegistrationTierViewSet, basename='registrationtier')
router.register(r'memberships', MembershipViewSet, basename='membership')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'speakers', SpeakerViewSet, basename='speaker')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('profile/', UserProfileView.as_view(), name='api-profile'),
    path('', include(router.urls)),
]
