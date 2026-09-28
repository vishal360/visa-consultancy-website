# V&P UkraLink — brand assets

Logo set and Instagram templates, matching the website's colours exactly. Every
file is **SVG**, so it scales to any size without going blurry — a logo should
never be stored as a fixed-size image.

## Getting PNGs for Instagram

Instagram will not accept SVG, so there is a converter included. No software to
install:

1. Open **`brand/export.html`** in any browser (double-click it — it works
   straight off your disk)
2. Pick an export size (**2x** is recommended — sharper on modern phones)
3. Click **Download PNG** on the ones you want, or **Download all**

The conversion happens inside your browser tab. Nothing is uploaded anywhere.

There is also a **Download all as JPG** button, which flattens the transparent
background to the brand navy — useful if a platform rejects PNG.

## What's here

### Logos — `brand/logo/`

| File | Use it for |
| --- | --- |
| `logo-icon.svg` | **Instagram profile picture**, favicon, app icon |
| `logo-stacked.svg` | Square spaces, posts, anywhere with limited width |
| `logo-horizontal.svg` | Website header, email signature, letterhead |
| `logo-mono-light.svg` | Single colour on dark backgrounds |
| `logo-mono-dark.svg` | Single colour on light backgrounds, faxes, stamps, embroidery |

For the **profile picture**, export `logo-icon` at 2x or 3x. Instagram crops it
to a circle, and the design was laid out so nothing important sits near the
corners — the route and both markers stay well inside the circle.

### Instagram posts — `brand/instagram/` (1080 x 1080)

| File | Subject |
| --- | --- |
| `01-intro.svg` | Who you are — good as a pinned first post |
| `02-visa-types.svg` | The six routes you handle |
| `03-student.svg` | Student visa and university placement |
| `04-work.svg` | Work permit and employment visa |
| `05-refusal.svg` | Refusal review — a strong differentiator |
| `06-book.svg` | Booking details, hours and contact |
| `story-template.svg` | 1080 x 1920 story, with a guide box for your own text |

## Editing the posts

The posts are generated from one template, so they cannot drift apart
stylistically. To change wording, edit the `POSTS` list in
[`generate_posts.py`](generate_posts.py) and re-run:

```bash
python3 brand/generate_posts.py
```

That rewrites the SVGs *and* rebuilds `export.html`. You can also open any `.svg`
in a text editor and change the words directly, or import it into Figma, Canva or
Illustrator if you would rather work visually.

## Design reference

### Colours

| Swatch | Hex | Where |
| --- | --- | --- |
| Deep navy | `#071531` | Backgrounds |
| Navy | `#0b1f4d` | Logo wordmark, dark surfaces |
| Azure | `#1b57d6` | Links, buttons on light backgrounds |
| Light azure | `#4d8dff` | Accents, gradients |
| Pale azure | `#8fbaff` | Secondary text on dark, origin marker |
| Gold | `#ffd700` | Primary accent, destination marker, CTAs |
| Deep gold | `#e6b422` | Gradient partner to gold |
| Muted text | `#9db0d0` | Body copy on dark backgrounds |

Navy and gold are a deliberate nod to the Ukrainian flag without copying it
outright.

### Typography

**Inter**, falling back to Segoe UI and the system sans-serif. Free from
[Google Fonts](https://fonts.google.com/specimen/Inter) if you want it installed
locally.

One caveat worth knowing: the text in these SVGs is *live text*, not converted to
outlines. If a machine lacks Inter it falls back to another sans-serif, so
exports may differ very slightly between computers. It will still look clean.
Export from one machine and reuse those PNGs if you want them pixel-identical.

### The mark

A route rising from a pale blue origin marker to a gold destination ring — the
"link" in UkraLink, being India to Ukraine. It stays legible down to 16px, which
is why the stroke is heavy and the two markers differ in both size and colour.

## Caption drafts

Starting points, in the same honest register as the website — no approval-rate
claims or invented client numbers, because none of that is verified.

**01 — Intro**
> Planning a move to Ukraine? Short-stay, student, work, business, family or
> residence — the first job is working out which route actually fits your
> situation. That is what we do.
> Consultations by video or phone. Link in bio.
> #UkraineVisa #StudyInUkraine #VisaConsultant #ImmigrationHelp

**02 — Visa types**
> Not sure which visa you need? Here are the six routes we handle. Any stay over
> 90 days, or any stay involving work, study or residence, needs a Type D visa
> regardless of nationality.
> Run our free eligibility checker — link in bio.
> #UkraineVisa #TypeDVisa #VisaGuide

**03 — Student**
> Heading to a Ukrainian university? We verify the university's accreditation
> *before* you pay any fees, obtain the official invitation, and get your
> certificates legalised and translated.
> #StudyInUkraine #StudentVisa #MBBSAbroad #StudyAbroad

**04 — Work**
> Got a job offer in Ukraine? Your employer has to obtain the employment permit
> before you can apply for the visa — a step people often discover too late. We
> deal with them directly.
> #WorkPermit #UkraineJobs #WorkAbroad

**05 — Refusal**
> A refused application is not the end. It is usually a fixable gap in the
> evidence, not a permanent bar. We find the real reason, then decide between an
> appeal and a corrected re-application.
> #VisaRefusal #VisaAppeal #UkraineVisa

**06 — Booking**
> Booking takes about two minutes. Pick a service, choose a slot, tell us about
> your case. Video or phone, 11am to 6pm IST, Monday to Friday.
> Fees are quoted on the call, once we understand what your case actually needs.
> #BookNow #VisaConsultation #UkraineVisa

## Before you publish

- Swap the website address for your custom domain once you have one — it appears
  on `01`, `02`, `03`, `04`, `05`, `06` and the story template, and is set in one
  place (`SITE`) at the top of `generate_posts.py`
- Claims on these posts are limited to services and process. If you later want
  to state figures, make sure you can evidence them
