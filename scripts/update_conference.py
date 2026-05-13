from conference.models import Conference, RegistrationTier, Track
from django.utils import timezone
from datetime import date, datetime

conf = Conference.objects.get(slug='iatm-2026-fall')

# Update conference details
conf.conference_description = """Navigating the Great Pivot: Business Transformation and Technology in the Regenerative Era.

The IATM 2026 (FALL) organizing committee invites scholars, practitioners, and students to submit their original work. This year's theme explores the "Great Pivot" and the "Regenerative Era" - a shift beyond mere sustainability toward business models and technologies that actively restore and renew our social, environmental, and economic systems.

This global gathering will bring together a dynamic community of scholars, practitioners, and industry leaders to engage in meaningful dialogue around some of the most critical issues of our time - responsible AI, ethics, sustainability, global impact, and emerging technological trends shaping our future.

Hosted at Indiana University of Pennsylvania, PA, USA."""
conf.early_bird_deadline = date(2026, 7, 30)
conf.submission_deadline = timezone.make_aware(datetime(2026, 6, 30, 23, 59, 59))
conf.member_discount_percent = 25
conf.save()
print('Conference updated')

# Delete old tiers
RegistrationTier.objects.filter(conference=conf).delete()
print('Old tiers removed')

# Create correct tiers per CFP
# Early Bird: till July 30
# Regular: till Aug 30
# Late: after Aug 30
# We use early_bird_price for the early bird rate, price for regular
# Late registration would need a separate mechanism or manual update after Aug 30
RegistrationTier.objects.create(
    conference=conf, name='Professional',
    price=225, early_bird_price=175,
    description='Industry professionals, faculty, and practitioners. Late registration (after Aug 30): $300.',
    is_active=True,
)
RegistrationTier.objects.create(
    conference=conf, name='Student',
    price=100, early_bird_price=75,
    description='Undergraduate and graduate students with valid student ID. Early rate: $75.',
    is_active=True,
)
RegistrationTier.objects.create(
    conference=conf, name='Virtual / Online',
    price=225, early_bird_price=175,
    description='Virtual attendance with access to all online sessions. 25% IATM member discount applies.',
    is_active=True,
)
RegistrationTier.objects.create(
    conference=conf, name='PhD Scholar',
    price=225, early_bird_price=175,
    description='PhD candidates. 25% IATM member discount applies.',
    is_active=True,
)
print('4 tiers created')

# Delete old tracks
Track.objects.filter(conference=conf).delete()
print('Old tracks removed')

# Create tracks per CFP
tracks = [
    'Regenerative Business Models',
    'Human-Centric Leadership',
    'Human Resources & Talent Management',
    'Strategy & Management',
    'Operations & Supply Chain',
    'Market Dynamics',
    'Technological Transformation',
    'Marketing & Consumer Behavior',
    'Finance & Accounting',
    'Technology & Analytics',
    'Education & Digital Pedagogies',
    'Policy & Ethics',
]
for t in tracks:
    Track.objects.create(conference=conf, name=t)
print(f'{len(tracks)} tracks created')

print('DONE - conference updated to match CFP')
