"""
Editorial content for the marketing site.

Kept in one place so the copy can be revised without touching templates or
route code. Everything here is escaped at render time.

NOTE: The visa facts below are illustrative placeholders for a demo site.
Replace them with figures verified against current Ukrainian State Migration
Service and MFA guidance before going live.
"""

from __future__ import annotations

VISA_TYPES: list[dict] = [
    {
        "id": "short-stay",
        "service_id": "tourist-c",
        "name": "Short-stay visa",
        "type_label": "Type C · up to 90 days",
        "icon": "🛬",
        "summary": (
            "For tourism, visiting family, conferences and short business trips. "
            "The most common first Ukrainian visa."
        ),
        "stay": "Up to 90 days in any 180",
        "processing": "5–15 working days",
        "entries": "Single, double or multiple",
        "highlights": [
            "Invitation letter drafted and checked by us",
            "Itinerary and accommodation evidence assembled",
            "Travel insurance meeting the minimum cover rules",
        ],
        "documents": [
            "Passport valid 3+ months beyond your return date",
            "Completed online application form",
            "Passport photo to ICAO specification",
            "Proof of accommodation for the whole stay",
            "Travel medical insurance (min. €30,000 cover)",
            "Evidence of sufficient funds",
        ],
    },
    {
        "id": "long-stay",
        "service_id": "long-d",
        "name": "Long-stay visa",
        "type_label": "Type D · 90+ days",
        "icon": "🗝️",
        "summary": (
            "The mandatory first step towards a temporary residence permit for "
            "work, study, family or business."
        ),
        "stay": "90 days, then convert to a residence permit",
        "processing": "10–30 working days",
        "entries": "Single or multiple entry",
        "highlights": [
            "Route mapped from visa through to residence permit",
            "Ministry-level document legalisation handled",
            "Registration with the migration service after arrival",
        ],
        "documents": [
            "Passport valid 6+ months beyond intended stay",
            "Purpose-specific grounds document (contract, invitation, enrolment)",
            "Police clearance certificate, apostilled",
            "Medical certificate including an HIV test",
            "Health insurance valid in Ukraine",
            "Proof of financial means",
        ],
    },
    {
        "id": "student",
        "service_id": "student",
        "name": "Student visa",
        "type_label": "Type D · study",
        "icon": "🎓",
        "summary": (
            "For accredited degree, preparatory and medical programmes at "
            "Ukrainian universities."
        ),
        "stay": "Duration of the study programme",
        "processing": "15–30 working days",
        "entries": "Multiple entry",
        "highlights": [
            "University accreditation verified before you pay any fees",
            "Official invitation obtained through the university registry",
            "Student residence permit and dormitory registration",
        ],
        "documents": [
            "Official university invitation registered with the ministry",
            "Legalised secondary or higher education certificates",
            "Academic transcripts with certified translations",
            "Proof of tuition payment",
            "Medical certificate and HIV test result",
            "Birth certificate, apostilled",
        ],
    },
    {
        "id": "work",
        "service_id": "work",
        "name": "Work permit & visa",
        "type_label": "Type D · employment",
        "icon": "💼",
        "summary": (
            "Employer-sponsored route covering the work permit, the entry visa "
            "and your residence registration."
        ),
        "stay": "Up to 3 years, renewable",
        "processing": "Permit 7–15 days, then visa 10–15 days",
        "entries": "Multiple entry",
        "highlights": [
            "Employment permit filed with the regional employment centre",
            "Contract reviewed against Ukrainian labour law",
            "Salary threshold and quota compliance checked",
        ],
        "documents": [
            "Employment permit issued to your employer",
            "Signed employment contract",
            "Passport copies of company signatories",
            "Police clearance certificate, apostilled",
            "Qualification and diploma documents, legalised",
            "Medical insurance valid in Ukraine",
        ],
    },
    {
        "id": "business",
        "service_id": "business",
        "name": "Business & investor",
        "type_label": "Type D · founder",
        "icon": "📈",
        "summary": (
            "Company formation, investor residency and relocating key staff to "
            "a Ukrainian entity."
        ),
        "stay": "Up to 3 years, renewable",
        "processing": "20–40 working days end to end",
        "entries": "Multiple entry",
        "highlights": [
            "LLC or representative office registered in your name",
            "Investment threshold structured correctly from day one",
            "Tax registration, banking and accounting introductions",
        ],
        "documents": [
            "Company registration extract",
            "Proof of foreign investment (from US$100,000)",
            "Founding documents with certified translations",
            "Bank confirmation of the transferred investment",
            "Passport and police clearance certificate",
            "Lease agreement for the registered office",
        ],
    },
    {
        "id": "family",
        "service_id": "family",
        "name": "Family reunification",
        "type_label": "Type D · family",
        "icon": "👨‍👩‍👧",
        "summary": (
            "Join a spouse, parent or child who is a Ukrainian citizen or "
            "permit holder."
        ),
        "stay": "Matched to your sponsor's status",
        "processing": "15–30 working days",
        "entries": "Multiple entry",
        "highlights": [
            "Relationship evidence prepared to migration-service standards",
            "Marriage and birth certificates legalised and translated",
            "Dependent children included in a single application",
        ],
        "documents": [
            "Marriage or birth certificate, apostilled",
            "Sponsor's passport or residence permit copy",
            "Sponsor's written invitation and proof of housing",
            "Evidence the sponsor can support you financially",
            "Police clearance certificate",
            "Medical certificate and HIV test result",
        ],
    },
    {
        "id": "residence",
        "service_id": "residence",
        "name": "Residence permits",
        "type_label": "TRP & PRP",
        "icon": "🪪",
        "summary": (
            "Convert your Type D visa into temporary residence, then progress "
            "towards permanent status."
        ),
        "stay": "TRP 1–3 years · PRP indefinite",
        "processing": "TRP 15 days · PRP up to 6 months",
        "entries": "Unlimited while valid",
        "highlights": [
            "Filed within the 15-day window after you arrive",
            "Renewals tracked so your status never lapses",
            "Path to permanent residence and citizenship mapped out",
        ],
        "documents": [
            "Valid Type D visa and passport",
            "Grounds document matching your visa category",
            "Proof of a registered address in Ukraine",
            "Tax identification number",
            "Biometric data captured at the migration service",
            "Paid administrative service fee receipt",
        ],
    },
    {
        "id": "appeal",
        "service_id": "appeal",
        "name": "Refusal review",
        "type_label": "Appeals & re-filing",
        "icon": "⚖️",
        "summary": (
            "Had an application refused? We diagnose the real reason and build "
            "a corrected case."
        ),
        "stay": "n/a",
        "processing": "Assessment within 48 hours",
        "entries": "n/a",
        "highlights": [
            "Line-by-line review of your refusal notice",
            "Missing or weak evidence identified and replaced",
            "Formal appeal or a stronger re-application, whichever wins",
        ],
        "documents": [
            "Original refusal notice",
            "Your complete previous application bundle",
            "Passport with any prior visa stamps",
            "Correspondence with the consulate",
        ],
    },
]

PROCESS_STEPS: list[dict] = [
    {
        "title": "Free eligibility check",
        "text": (
            "Answer a few questions in our checker, or book a short orientation "
            "call. We tell you honestly which route fits and what it costs."
        ),
        "duration": "15 minutes",
    },
    {
        "title": "Strategy consultation",
        "text": (
            "A licensed consultant reviews your situation in depth, confirms the "
            "right visa category and hands you a written document checklist."
        ),
        "duration": "45–60 minutes",
    },
    {
        "title": "Document preparation",
        "text": (
            "We collect, translate, notarise and apostille everything, checking "
            "each item against current consular requirements before submission."
        ),
        "duration": "1–3 weeks",
    },
    {
        "title": "Submission & tracking",
        "text": (
            "Your application is filed at the correct consulate or migration "
            "office. We monitor progress and answer any official queries."
        ),
        "duration": "5–30 working days",
    },
    {
        "title": "Arrival & registration",
        "text": (
            "Once approved, we brief you on entry formalities and handle your "
            "residence permit registration within the legal 15-day window."
        ),
        "duration": "First 2 weeks in Ukraine",
    },
]

STATS: list[dict] = [
    {"value": "2400", "suffix": "+", "label": "Applications handled"},
    {"value": "96", "suffix": "%", "label": "Approval rate"},
    {"value": "38", "suffix": "", "label": "Nationalities served"},
    {"value": "11", "suffix": " yrs", "label": "In Ukrainian immigration law"},
]

TESTIMONIALS: list[dict] = [
    {
        "name": "Adaeze O.",
        "initials": "AO",
        "detail": "Medical student · Lagos → Kharkiv",
        "rating": 5,
        "text": (
            "My first application was refused for missing legalisation. They "
            "spotted it in ten minutes, rebuilt the file and I had my student "
            "visa five weeks later."
        ),
    },
    {
        "name": "Martin K.",
        "initials": "MK",
        "detail": "IT contractor · Berlin → Kyiv",
        "rating": 5,
        "text": (
            "The work permit process looked impossible from the outside. They "
            "dealt with my employer directly and I only had to sign things."
        ),
    },
    {
        "name": "Priya S.",
        "initials": "PS",
        "detail": "Family reunification · Mumbai → Lviv",
        "rating": 5,
        "text": (
            "Clear answers, fixed fees and no false promises. They told me one "
            "route would not work, which saved me months."
        ),
    },
    {
        "name": "Tomasz W.",
        "initials": "TW",
        "detail": "Founder · Warsaw → Odesa",
        "rating": 4,
        "text": (
            "Registered my company and sorted investor residency in under two "
            "months. The document checklist alone was worth the fee."
        ),
    },
    {
        "name": "Amina B.",
        "initials": "AB",
        "detail": "Tourist visa · Istanbul → Kyiv",
        "rating": 5,
        "text": (
            "Booked a consultation on a Sunday evening and had a reply first "
            "thing Monday. Simple, fast and genuinely helpful."
        ),
    },
]

FAQS: list[dict] = [
    {
        "question": "Do I need a visa to enter Ukraine?",
        "answer": (
            "It depends on your citizenship and purpose of travel. Many "
            "nationalities enjoy visa-free short stays, while others need a "
            "Type C visa. Any stay beyond 90 days, or any stay involving work, "
            "study or residence, requires a Type D visa regardless of "
            "nationality. Our eligibility checker gives you an instant "
            "indication, and we confirm it in your consultation."
        ),
    },
    {
        "question": "How long does the whole process take?",
        "answer": (
            "A short-stay visa is typically 5–15 working days once documents "
            "are complete. Long-stay routes take longer because of "
            "legalisation and apostille steps — usually four to ten weeks from "
            "your first consultation to visa in hand. Document gathering, not "
            "the consulate, is normally the slowest part."
        ),
    },
    {
        "question": "What happens in the consultation?",
        "answer": (
            "A consultant reviews your passport history, purpose of travel and "
            "any previous refusals, then confirms the correct visa category. "
            "You leave with a written checklist tailored to your case, a "
            "realistic timeline and a fixed quote. Sessions run 45–60 minutes "
            "by video, phone or at our Kyiv office."
        ),
    },
    {
        "question": "Can you help if I was refused before?",
        "answer": (
            "Yes, and it is a large part of what we do. Refusals are usually "
            "caused by fixable evidentiary gaps rather than a permanent bar. We "
            "review your refusal notice and original bundle, then decide "
            "whether a formal appeal or a corrected re-application gives you "
            "the better chance."
        ),
    },
    {
        "question": "What are your fees?",
        "answer": (
            "Consultations are charged at the fixed rate shown next to each "
            "service, and the orientation call is free. Full case handling is "
            "quoted as a fixed fee after your consultation, so you always know "
            "the total before committing. Government and consular fees are "
            "separate and paid directly to the authorities."
        ),
    },
    {
        "question": "Do you guarantee my visa will be approved?",
        "answer": (
            "No honest adviser can. The decision rests solely with the "
            "consulate or migration service. What we guarantee is that your "
            "application will be complete, correctly legalised and filed on "
            "time — the factors that actually sit within our control."
        ),
    },
    {
        "question": "Do you handle translation and apostille?",
        "answer": (
            "Yes. We arrange certified Ukrainian translations, notarisation and "
            "apostille or consular legalisation as your case requires, and we "
            "check every document against the standards the receiving "
            "authority applies."
        ),
    },
    {
        "question": "Is my personal data safe?",
        "answer": (
            "Your details are stored only to deliver the service you asked for "
            "and are never sold or shared with third parties beyond the "
            "authorities handling your application. You can request deletion of "
            "your record at any time by emailing us."
        ),
    },
]

# Interactive eligibility checker. Each answer contributes weight to one or more
# services; the highest-scoring service becomes the recommendation.
WIZARD: dict = {
    "intro": (
        "Four quick questions and we'll point you at the right Ukrainian visa "
        "route. No email required."
    ),
    "questions": [
        {
            "id": "purpose",
            "label": "Why are you travelling to Ukraine?",
            "options": [
                {"label": "Tourism or visiting family", "scores": {"tourist-c": 3}},
                {"label": "Study at a university", "scores": {"student": 4}},
                {"label": "Employment with a Ukrainian employer", "scores": {"work": 4}},
                {"label": "Starting or running a business", "scores": {"business": 4}},
                {"label": "Joining my spouse, parent or child", "scores": {"family": 4}},
                {"label": "Living here long term", "scores": {"residence": 3, "long-d": 2}},
            ],
        },
        {
            "id": "duration",
            "label": "How long do you plan to stay?",
            "options": [
                {"label": "A few weeks", "scores": {"tourist-c": 3}},
                {"label": "Up to 90 days", "scores": {"tourist-c": 2}},
                {"label": "Several months to a year", "scores": {"long-d": 3}},
                {"label": "More than a year", "scores": {"residence": 3, "long-d": 1}},
            ],
        },
        {
            "id": "history",
            "label": "Have you applied for a Ukrainian visa before?",
            "options": [
                {"label": "No, this is my first application", "scores": {}},
                {"label": "Yes, and it was approved", "scores": {}},
                {"label": "Yes, but it was refused", "scores": {"appeal": 5}},
                {"label": "I currently hold a Ukrainian visa", "scores": {"residence": 2}},
            ],
        },
        {
            "id": "timeline",
            "label": "When do you need to travel?",
            "options": [
                {"label": "Within a month", "scores": {}},
                {"label": "In one to three months", "scores": {}},
                {"label": "In three to six months", "scores": {}},
                {"label": "Still researching", "scores": {"other": 1}},
            ],
        },
    ],
    # Shown alongside the recommended service.
    "outcomes": {
        "tourist-c": {
            "title": "Short-stay visa (Type C)",
            "text": (
                "Your trip fits the short-stay category. Expect a 5–15 working "
                "day decision once your documents are in order."
            ),
        },
        "long-d": {
            "title": "Long-stay visa (Type D)",
            "text": (
                "You'll need a Type D visa, then a residence permit after "
                "arrival. Legalising documents is the step to start early."
            ),
        },
        "student": {
            "title": "Student visa",
            "text": (
                "You need a registered university invitation plus legalised "
                "education certificates. We verify accreditation first."
            ),
        },
        "work": {
            "title": "Work permit & employment visa",
            "text": (
                "Your employer must obtain an employment permit before you "
                "apply. We can deal with them directly."
            ),
        },
        "business": {
            "title": "Business & investor route",
            "text": (
                "Company structure and investment evidence drive this "
                "application. Getting it right from day one avoids re-filing."
            ),
        },
        "family": {
            "title": "Family reunification",
            "text": (
                "Relationship evidence and your sponsor's status are decisive. "
                "Certificates need apostille and certified translation."
            ),
        },
        "residence": {
            "title": "Temporary / permanent residence",
            "text": (
                "You're heading for a residence permit. The 15-day "
                "registration window after arrival is strict — plan for it."
            ),
        },
        "appeal": {
            "title": "Refusal review & appeal",
            "text": (
                "A previous refusal changes the strategy. We diagnose the real "
                "reason before deciding between appeal and re-application."
            ),
        },
        "other": {
            "title": "Free orientation call",
            "text": (
                "Your plans are still taking shape, so start with a free "
                "30-minute call to narrow the options."
            ),
        },
    },
}

TRUST_BADGES: list[dict] = [
    {"icon": "⚖️", "label": "Licensed immigration advisers"},
    {"icon": "🔒", "label": "GDPR-compliant data handling"},
    {"icon": "💬", "label": "Support in 6 languages"},
    {"icon": "📄", "label": "Fixed fees, quoted upfront"},
]
