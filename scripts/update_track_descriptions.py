from conference.models import Track

descriptions = {
    'Regenerative Business Models': 'Redesigning organizational frameworks through circular economies, net-positive value creation, and supply chains that restore rather than deplete resources.',
    'Human-Centric Leadership': 'Navigating the "Great Pivot" by prioritizing holistic employee wellness and ethical stewardship in an increasingly automated work environment.',
    'Human Resources & Talent Management': 'Reimagining the future of work through regenerative HR practices that foster long-term human flourishing and organizational resilience.',
    'Strategy & Management': 'Orchestrating the transformation of legacy models into agile, socially entrepreneurial ventures capable of thriving in a regenerative economy.',
    'Operations & Supply Chain': 'Transitioning toward Industry 5.0 and sustainable logistics to build global supply networks that are both resilient and restorative.',
    'Market Dynamics': 'Analyzing the evolution of consumer behavior in post-digital markets and the ethical imperatives of green marketing.',
    'Technological Transformation': 'Harnessing AI, machine learning, and Digital Twins to solve systemic social challenges and ensure radical transparency via blockchain.',
    'Marketing & Consumer Behavior': 'Moving beyond traditional sales toward ethical branding and conscious consumerism that empowers the regenerative mindset.',
    'Finance & Accounting': 'Evolving from traditional reporting to regenerative finance, impact investing, and fintech solutions that drive equitable social and environmental outcomes.',
    'Technology & Analytics': 'Leveraging Big Data and automation as ethical catalysts for restorative growth while safeguarding data integrity and human value.',
    'Education & Digital Pedagogies': 'Innovating business curricula through gamification and immersive VR training to prepare the next generation of regenerative leaders.',
    'Policy & Ethics': 'Developing robust governance frameworks and algorithmic accountability to ensure emerging technologies serve the public good and ecological health.',
}

updated = 0
for name, desc in descriptions.items():
    count = Track.objects.filter(name=name).update(description=desc)
    updated += count

print(f'Updated {updated} track descriptions')
