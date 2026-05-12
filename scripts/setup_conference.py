from conference.models import Conference, RegistrationTier, Track, PromoCode
from schedule.models import Session, Speaker, Room
from django.utils import timezone
from datetime import date, datetime, timedelta

conf = Conference.objects.create(
    conference_name='IATM 2026 (FALL) International Conference',
    conference_description='Navigating the Great Pivot: Business Transformation and Technology in the Regenerative Era.',
    start_date=date(2026, 11, 19),
    end_date=date(2026, 11, 21),
    location='Indiana University of Pennsylvania, PA, USA',
    slug='iatm-2026-fall',
    early_bird_deadline=date(2026, 8, 31),
    member_discount_percent=15,
    submission_deadline=timezone.make_aware(datetime(2026, 9, 30, 23, 59, 59)),
    review_deadline=timezone.make_aware(datetime(2026, 10, 31, 23, 59, 59)),
    blind_review=True,
)
print('Conference created')

for n, p, e in [('Student', 50, 35), ('Academic', 100, 75), ('Professional', 150, 120), ('Virtual', 30, 20)]:
    RegistrationTier.objects.create(conference=conf, name=n, price=p, early_bird_price=e)
print('4 tiers created')

for t in ['Responsible AI & Ethics', 'Digital Transformation & Innovation', 'Cybersecurity & Data Privacy', 'Sustainability & Regenerative Business', 'Global Impact & Socio-Economic Trends', 'Emerging Technologies']:
    Track.objects.create(conference=conf, name=t)
print('6 tracks created')

PromoCode.objects.create(
    conference=conf, code='IATM2026', discount_type='percentage',
    discount_value=20, max_uses=100,
    valid_from=timezone.now(),
    valid_until=timezone.now() + timedelta(days=365),
    is_active=True,
)
print('Promo code IATM2026 created')

for r in ['Auditorium A', 'Room 201', 'Room 202', 'Workshop Lab']:
    Room.objects.create(conference=conf, name=r, capacity=100)
print('4 rooms created')

for fn, ln, org in [('Larry', 'Pickett', 'IUP'), ('Jane', 'Smith', 'MIT'), ('Raj', 'Patel', 'Stanford')]:
    Speaker.objects.create(first_name=fn, last_name=ln, organization=org)
print('3 speakers created')

print('DONE - visit /conference/iatm-2026-fall/ to see it')
