# IATM Conference Management Tool - What's Left

**Generated**: 2026-03-17
**Overall Completion**: ~82-85% of core requirements

---

## Summary by Area

| Area | Status | Completion |
|------|--------|------------|
| User Auth & Profiles | Done (SSO missing) | 60% |
| Registration & Payments | Done (no Stripe) | 95% |
| Paper & Review Workflow | Done | 95% |
| Virtual & Zoom Integration | Done (no streaming) | 90% |
| Email Communication | System ready, SMTP not configured | 75% |
| Event Experience | Schedule, speakers, networking work | 85% |
| Admin Command Center | Analytics, exports, dashboards exist | 85% |
| Technical Must-Haves | i18n, responsive, SSL configured | 80% |

---

## Critical Path to Production

These must be done before going live:

- [ ] **Configure production email SMTP** — set real credentials in `.env` (SendGrid/Mailgun/Gmail)
- [ ] **Set up PayPal live credentials** — swap sandbox keys for production
- [ ] **Configure SSL certificates** — run Certbot for Let's Encrypt
- [ ] **Test end-to-end payment flow** — full PayPal cycle in production
- [ ] **Set up database backups** — automated backup strategy
- [ ] **Set up error monitoring** — Sentry or similar
- [ ] **Load test** — ensure Gunicorn worker count is sufficient
- [ ] **Security audit** — vulnerability scan, penetration testing

---

## Missing Features

### High Priority

#### 1. Email SMTP Not Configured for Production
- Email backend defaults to `console.EmailBackend` (prints to terminal)
- All email functions are written and ready — just needs SMTP credentials in `.env`
- No async email sending (emails block the request)
- **Action**: Add SendGrid/Mailgun credentials to `.env`, switch backend to `smtp.EmailBackend`

#### 2. No Tests Written
- Test files exist in every app but are all empty (`# Create your tests here.`)
- No unit, integration, or end-to-end tests
- **Action**: Write tests for models, views, forms, permissions, and payment flow

#### 3. No CI/CD Pipeline
- No GitHub Actions, GitLab CI, or any automated pipeline
- **Action**: Add workflow for linting, testing, building Docker image, and deploying

#### 4. Remove Duplicate Payment Module
- `/cm/payments/` is a legacy/unused payment module (not in `INSTALLED_APPS`)
- Active payments live in `/conference/` app
- **Action**: Delete `cmt project/cm/payments/` directory

#### 5. No Rate Limiting
- No protection against brute-force login attempts or API abuse
- **Action**: Add `django-ratelimit` or similar middleware

### Medium Priority

#### 6. No REST API
- Entire system is Django view-based, no JSON API endpoints
- No Django REST Framework installed
- **Action**: Add DRF, create API endpoints for conferences, submissions, reviews, payments

#### 7. No Background Task Queue (Celery)
- All operations are synchronous (emails, PDF generation, etc.)
- No scheduled tasks (e.g., reminder emails before deadlines)
- **Action**: Set up Celery + Redis, move email sending and PDF generation to async tasks

#### 8. No SSO / OAuth Integration
- Authentication is standalone email-based only
- No integration with IATM association site or external identity providers
- **Action**: Add `django-allauth` or SAML integration if needed

#### 9. Incomplete GDPR Compliance
- Export data and delete account exist
- Missing: cookie consent banner, data retention policies, audit logging, breach notification
- **Action**: Add `django-cookie-consent`, implement audit trail

#### 10. No Stripe Payment Option
- Only PayPal is supported
- **Action**: Add Stripe as alternative payment gateway

#### 11. Advanced Scheduling Features Missing
- No conflict detection for overlapping sessions
- No room/venue management or capacity tracking
- No iCalendar export for attendees
- **Action**: Add room model, conflict validation, `.ics` export

#### 12. No Refund Handling
- Payments can be captured but not refunded through the system
- No discount codes / coupon system
- **Action**: Implement PayPal refund API, add promo code model

### Low Priority

#### 13. No Application Monitoring / Logging
- No APM (Sentry, New Relic, Datadog)
- No centralized logging (ELK stack)
- No uptime monitoring
- **Action**: Integrate Sentry for errors, set up basic health check monitoring

#### 14. Incomplete Internationalization
- 5 languages configured (EN, ES, FR, ZH, AR) with i18n URL patterns
- Translation `.po` files likely incomplete
- **Action**: Run `makemessages`, complete translations, test RTL for Arabic

#### 15. Accessibility (WCAG) Not Verified
- Bootstrap 5 provides baseline accessibility
- No ARIA labels audit, keyboard nav testing, or screen reader testing
- **Action**: Run accessibility audit (axe, Lighthouse), fix issues

#### 16. No Progressive Web App (PWA) Support
- Responsive design works on mobile but no offline support or push notifications
- **Action**: Add service worker, manifest.json, push notifications if needed

#### 17. Advanced Analytics Missing
- Basic dashboard with counts exists
- No charts/graphs (Chart.js), no scheduled reports, no cohort analysis
- **Action**: Add Chart.js to analytics dashboard, scheduled CSV email reports

#### 18. Documentation Gaps
- README, EMAIL_SETUP.md, PAYPAL_SETUP.md exist
- Missing: architecture docs, DB schema diagram, admin user guide, troubleshooting guide
- **Action**: Create docs as needed

---

## Technical Debt

| Issue | Location | Impact |
|-------|----------|--------|
| Unused payment module | `cm/payments/` | Confusion, dead code |
| Empty test files | All `tests.py` files | No test coverage |
| Synchronous email sending | `submissions/emails.py` | Slow request handling |
| No pagination on some list views | Various views | Performance with large datasets |
| Mixed permission patterns | Various views | Inconsistent `@login_required` vs manual `is_staff` checks |
| Hardcoded paths in email templates | `submissions/emails/` | Breaks if deployed to subpath |
| No Content Security Policy | `settings.py` | XSS protection gap |
| No CORS configuration | `settings.py` | Blocks future API consumers |

---

## What's Already Complete and Working

For reference, these features are fully implemented:

- Email-based user auth (register, login, password reset, GDPR export/delete)
- Profile editing (name, phone, country, organization, occupation)
- Conference CRUD with tracks and registration tiers (early bird, member discounts)
- Membership with roles (Author, Reviewer, Chair), payment tracking
- Paper submissions with co-authors, status workflow, digital proceedings
- Peer review system with blind review, auto-status updates, notifications
- PayPal payments with invoice PDF generation
- Schedule builder with sessions, speakers, Zoom integration, attendance tracking
- Networking hub with attendee directory, messaging, group registration
- Admin analytics dashboard with CSV exports, bulk email, badge/QR generation
- Docker + Docker Compose (dev & prod), Nginx, Gunicorn, SSL config
- Security hardening (HSTS, secure cookies, CSRF, XSS headers)
- Internationalization setup (5 languages, URL routing, language switcher)
