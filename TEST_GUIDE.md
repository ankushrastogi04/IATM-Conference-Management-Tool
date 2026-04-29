# IATM Conference Management Tool - End-to-End Test Guide

**App URL**: http://localhost:8000  
**Admin Panel**: http://localhost:8000/admin/  
**API Root**: http://localhost:8000/api/

---

## Test Accounts

| Email | Password | Role | Purpose |
|-------|----------|------|---------|
| `ankushrastogi04@gmail.com` | `Test@1234` | Admin / Staff | Full access, admin dashboard, analytics, assign roles |
| `author@test.com` | `Test@1234` | Author | Register, pay, submit paper, view reviews |
| `reviewer@test.com` | `Test@1234` | Reviewer | Review assigned papers |
| `chair@test.com` | `Test@1234` | Chair | Assign reviewers, manage submissions |

**Promo Code**: `IATM2026` (20% off any tier)

---

## Conference Created

**IATM 2026 (FALL) International Conference**
- Dates: November 19-21, 2026
- Location: Indiana University of Pennsylvania, PA, USA
- Early Bird Deadline: August 31, 2026 (early bird pricing is currently ACTIVE)
- Submission Deadline: September 30, 2026
- Review Deadline: October 31, 2026
- Blind Review: Enabled

**Registration Tiers** (early bird / regular):
| Tier | Early Bird | Regular |
|------|-----------|---------|
| Student | $35 | $50 |
| Academic | $75 | $100 |
| Professional | $120 | $150 |
| Virtual | $20 | $30 |

**Tracks**: Responsible AI & Ethics, Digital Transformation & Innovation, Cybersecurity & Data Privacy, Sustainability & Regenerative Business, Global Impact & Socio-Economic Trends, Emerging Technologies

**Schedule**: 7 sessions across 3 days (keynote, papers, workshop, panel, break, social)

---

## Test Flow - Step by Step

### Step 1: Register & Pay as Author

1. Open http://localhost:8000/accounts/login/
2. Login with `author@test.com` / `Test@1234`
3. Click **Conferences** in the sidebar
4. Click **IATM 2026 (FALL) International Conference**
5. Click **Register** and select Role 1 = **Author**, Role 2 = N/A
6. After registering, click **Pay** to go to the checkout page
7. You should see 4 tiers with **early bird prices** (since the deadline is Aug 2026)
8. Select **Student** tier ($35 early bird)
9. Enter promo code: `IATM2026` (should apply 20% off → $28)
10. Click **Pay with PayPal** — you'll be redirected to the PayPal payment page
11. Complete payment on PayPal
12. Return to the app and click the **confirmation link** to finalize registration
13. You should see a success message and your membership is now paid

**Verify**: 
- Check your email (`ankushrastogi04@gmail.com` if forwarded, or check console logs) for the registration confirmation email with PDF invoice
- Go to **Dashboard** — you should see your paid membership

---

### Step 2: Submit a Paper

1. Still logged in as `author@test.com`
2. Click **My Submissions** in sidebar, then click **Submit New Paper** (or go to the conference page and find the submit link)
3. Go to: http://localhost:8000/submissions/create/iatm-2026-fall/
4. Fill in:
   - **Paper Title**: "Ethical AI Frameworks for Business Transformation"
   - **Track**: Responsible AI & Ethics
   - **File**: Upload any PDF file
   - **Co-Author 1**: (leave blank or enter another user's email)
5. Click **Submit**
6. You should see the submission detail page with status **Pending**

**Verify**:
- Check email for submission confirmation
- Go to **My Submissions** — paper should appear in the list

---

### Step 3: Admin Setup - Assign Roles

1. **Logout** and login as `ankushrastogi04@gmail.com` / `Test@1234`
2. Go to **Conferences** → **IATM 2026 (FALL)** → **Admin Dashboard**
   (URL: http://localhost:8000/conference/iatm-2026-fall/admin-dashboard/)
3. You should see all registered members

**Register the reviewer and chair first** (they need to register for the conference):
4. Open a new incognito/private window
5. Login as `reviewer@test.com` / `Test@1234`
6. Go to Conferences → IATM 2026 → Register with Role 1 = **Reviewer**
7. Logout, login as `chair@test.com` / `Test@1234`
8. Go to Conferences → IATM 2026 → Register with Role 1 = **Chair**

**Now back in the admin window**:
9. Refresh the Admin Dashboard — you should see all 3 members
10. For `reviewer@test.com`: verify Role 1 = Reviewer
11. For `chair@test.com`: verify Role 1 = Chair
12. Use the **Payment toggle** buttons to mark reviewer and chair as paid (so they can access all features)

**Verify**:
- Click **Analytics** link (http://localhost:8000/membership/iatm-2026-fall/analytics/)
- You should see charts: registration doughnut, role bars, country distribution, occupation breakdown
- Try **Export Attendees CSV** and **Export Financials CSV**

---

### Step 4: Assign Reviewers (as Chair)

1. Login as `chair@test.com` / `Test@1234`
2. In the sidebar, click **Assign Reviewers**
3. Select conference: **IATM 2026 (FALL)**
4. You should see the submitted paper "Ethical AI Frameworks..."
5. Click **Assign** next to the paper
6. Select `Bob Reviewer (reviewer@test.com)` from the reviewer list
7. Click **Assign Reviewers**

**Verify**:
- Reviewer should receive an email notification about the assignment

---

### Step 5: Submit a Review (as Reviewer)

1. Login as `reviewer@test.com` / `Test@1234`
2. Click **Reviewer Dashboard** in the sidebar
3. You should see 1 pending review: "Ethical AI Frameworks..."
4. Note: Since **blind review** is enabled, you won't see author names
5. Click **Submit Review**
6. Enter:
   - **Comment**: "Well-structured paper with strong methodology. The ethical framework proposed is comprehensive and practical."
   - **Recommendation**: **Accept**
7. Click **Submit**

**Verify**:
- Review should appear in "Submitted Reviews" tab
- Completion rate should show 100%
- Author should receive email notification about the review

---

### Step 6: Check Review Decision (as Author)

1. Login as `author@test.com` / `Test@1234`
2. Click **View My Reviews** in the sidebar
3. You should see the review with recommendation: **Accept**
4. Go to **My Submissions** → click the paper
5. Status should now show **Accepted**

**Verify**:
- Author should have received a decision email ("Paper Accepted: Ethical AI Frameworks...")
- Go to **Proceedings** in the sidebar — the paper should appear in the accepted papers archive

---

### Step 7: Test Schedule & iCal Export

1. Login with any account
2. Go to the conference page → **Schedule** 
   (URL: http://localhost:8000/schedule/iatm-2026-fall/schedule/)
3. You should see sessions grouped by date (Nov 19, 20, 21)
4. Try the filters: filter by track, session type, date
5. Click **Speakers** to see the speaker directory
6. Click **Export iCal** to download the `.ics` file
   (URL: http://localhost:8000/schedule/iatm-2026-fall/schedule/export/)
7. Open the `.ics` file in your calendar app — you should see all 7 sessions

---

### Step 8: Test Networking Hub & Messaging

1. Login as `author@test.com` (must be a paid member)
2. Go to the conference page → **Networking Hub**
   (URL: http://localhost:8000/membership/iatm-2026-fall/networking/)
3. You should see paid attendees listed
4. Try searching by name or organization
5. Click **Send Message** next to another paid attendee
6. Send a test message

**Verify**:
- Go to **Messages** in the sidebar — you should see the sent message
- Login as the recipient — check their Messages inbox

---

### Step 9: Test Dashboard & Invoices

1. Login as `author@test.com`
2. Click **Dashboard** in the sidebar
   (URL: http://localhost:8000/conference/dashboard/)
3. You should see:
   - Your conference memberships
   - Payment history with invoice download link
   - Your submissions
   - Upcoming sessions
4. Click **Download Invoice** — should download a PDF invoice
5. Try **Download Badge** and **Download QR Ticket** (from membership links)

---

### Step 10: Test REST API

Open these URLs in a browser (you must be logged in):

| Endpoint | What you'll see |
|----------|----------------|
| http://localhost:8000/api/ | API root with all available endpoints |
| http://localhost:8000/api/conferences/ | List of conferences |
| http://localhost:8000/api/conferences/iatm-2026-fall/ | Conference detail |
| http://localhost:8000/api/sessions/ | Published sessions |
| http://localhost:8000/api/speakers/ | Speaker directory |
| http://localhost:8000/api/memberships/ | Your memberships |
| http://localhost:8000/api/submissions/ | Your submissions |
| http://localhost:8000/api/payments/ | Your payments |
| http://localhost:8000/api/profile/ | Your user profile (supports PATCH) |

---

### Step 11: Test Admin Panel

1. Login as `ankushrastogi04@gmail.com`
2. Go to http://localhost:8000/admin/
3. You can manage all models: Users, Conferences, Memberships, Submissions, Reviews, Payments, Sessions, PromoCode, Rooms, etc.

---

### Step 12: Test PWA

1. Open http://localhost:8000 on your phone (same network) or Chrome DevTools mobile view
2. Chrome should show "Add to Home Screen" prompt
3. The app works offline for cached pages (static assets are cached by service worker)

---

### Step 13: Test Cookie Consent

1. Open http://localhost:8000 in a private/incognito window
2. You should see a cookie consent banner at the bottom
3. Click **Accept** — it disappears and doesn't show again

---

## Quick Links

| Page | URL |
|------|-----|
| Login | http://localhost:8000/accounts/login/ |
| Register | http://localhost:8000/accounts/register/ |
| Conference List | http://localhost:8000/conference/ |
| IATM 2026 Detail | http://localhost:8000/conference/iatm-2026-fall/ |
| Payment Checkout | http://localhost:8000/conference/payment/iatm-2026-fall/ |
| Submit Paper | http://localhost:8000/submissions/create/iatm-2026-fall/ |
| Schedule | http://localhost:8000/schedule/iatm-2026-fall/schedule/ |
| Speakers | http://localhost:8000/schedule/iatm-2026-fall/speakers/ |
| iCal Export | http://localhost:8000/schedule/iatm-2026-fall/schedule/export/ |
| Networking Hub | http://localhost:8000/membership/iatm-2026-fall/networking/ |
| Admin Dashboard | http://localhost:8000/conference/iatm-2026-fall/admin-dashboard/ |
| Analytics | http://localhost:8000/membership/iatm-2026-fall/analytics/ |
| User Dashboard | http://localhost:8000/conference/dashboard/ |
| Proceedings | http://localhost:8000/submissions/proceedings/ |
| API Root | http://localhost:8000/api/ |
| Django Admin | http://localhost:8000/admin/ |
