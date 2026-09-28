#!/usr/bin/env python3
"""
Generate the Instagram assets as SVG.

Every post shares one template, so spacing, colours and the logo lockup stay
consistent by construction rather than by careful copy-pasting. To change the
wording, edit POSTS below and re-run:

    python3 brand/generate_posts.py

Copy is deliberately factual — services, process and hours only. No approval
rates, client counts or years-in-business, because none of those are verified.
"""

from __future__ import annotations

import html
from pathlib import Path

OUT = Path(__file__).parent / "instagram"

# Palette lifted from static/css/styles.css so the posts match the website.
INK = "#071531"
INK_2 = "#0f2550"
GOLD = "#ffd700"
GOLD_DIM = "#e6b422"
BLUE = "#4d8dff"
BLUE_SOFT = "#8fbaff"
MUTED = "#9db0d0"
WHITE = "#ffffff"

FONT = ("Inter, 'Segoe UI', system-ui, -apple-system, "
        "'Helvetica Neue', Arial, sans-serif")

SITE = "visa-consultancy.onrender.com"
EMAIL = "vpukralink@gmail.com"


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def _defs() -> str:
    return f"""  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="{INK_2}"/>
      <stop offset="1" stop-color="{INK}"/>
    </linearGradient>
    <linearGradient id="route" x1="0" y1="1" x2="1" y2="0">
      <stop offset="0" stop-color="{BLUE}"/>
      <stop offset="0.55" stop-color="{GOLD_DIM}"/>
      <stop offset="1" stop-color="{GOLD}"/>
    </linearGradient>
    <radialGradient id="orbGold" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{GOLD}" stop-opacity="0.20"/>
      <stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="orbBlue" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{BLUE}" stop-opacity="0.26"/>
      <stop offset="1" stop-color="{BLUE}" stop-opacity="0"/>
    </radialGradient>
  </defs>"""


def _background(w: int, h: int) -> str:
    """Gradient, two soft orbs and a faint grid — echoes the website hero."""
    lines = []
    for x in range(0, w + 1, 90):
        lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}"/>')
    for y in range(0, h + 1, 90):
        lines.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}"/>')
    grid = "".join(lines)
    return f"""  <rect width="{w}" height="{h}" fill="url(#bg)"/>
  <g stroke="{BLUE_SOFT}" stroke-width="1" opacity="0.055">{grid}</g>
  <circle cx="{int(w*0.88)}" cy="{int(h*0.12)}" r="{int(w*0.42)}" fill="url(#orbGold)"/>
  <circle cx="{int(w*0.06)}" cy="{int(h*0.80)}" r="{int(w*0.46)}" fill="url(#orbBlue)"/>"""


def _mark(x: float, y: float, size: float) -> str:
    """The logo badge, scaled to `size` pixels."""
    s = size / 512
    return f"""  <g transform="translate({x} {y}) scale({s:.6f})">
    <rect width="512" height="512" rx="116" fill="#16376f"/>
    <path d="M138 372C206 372 244 206 374 156" fill="none" stroke="url(#route)"
          stroke-width="30" stroke-linecap="round"/>
    <circle cx="138" cy="372" r="27" fill="{BLUE_SOFT}"/>
    <circle cx="374" cy="156" r="38" fill="{GOLD}"/>
    <circle cx="374" cy="156" r="15" fill="{INK}"/>
  </g>"""


def _lockup(pad: int, y: int, size: int = 66) -> str:
    """Logo + wordmark, for the top of each post."""
    return f"""{_mark(pad, y, size)}
  <text x="{pad + size + 22}" y="{y + size * 0.70:.0f}" font-family="{FONT}"
        font-size="34" font-weight="700" letter-spacing="-0.7">
    <tspan fill="{GOLD}">V&amp;P</tspan><tspan fill="{WHITE}" dx="8">UkraLink</tspan>
  </text>"""


def build_post(
    slug: str,
    eyebrow: str,
    headline: list[str],
    body: list[str] | None = None,
    bullets: list[str] | None = None,
    footer: str = SITE,
    cta: str | None = None,
) -> str:
    w = h = 1080
    pad = 88
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(" ".join(headline))}">',
        f"  <title>{esc(' '.join(headline))}</title>",
        _defs(),
        _background(w, h),
        _lockup(pad, 74),
    ]

    # Eyebrow
    parts.append(
        f'  <text x="{pad}" y="284" font-family="{FONT}" font-size="25" '
        f'font-weight="700" letter-spacing="4.6" fill="{GOLD}">{esc(eyebrow.upper())}</text>'
    )
    parts.append(
        f'  <rect x="{pad}" y="304" width="70" height="4" rx="2" fill="{GOLD}"/>'
    )

    # Headline
    size = 78 if max(len(l) for l in headline) <= 19 else 66
    step = int(size * 1.17)
    y = 300 + 96
    for line in headline:
        parts.append(
            f'  <text x="{pad}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="700" letter-spacing="-2" fill="{WHITE}">{esc(line)}</text>'
        )
        y += step

    y += 18

    # Body paragraph
    if body:
        for line in body:
            parts.append(
                f'  <text x="{pad}" y="{y}" font-family="{FONT}" font-size="33" '
                f'font-weight="400" fill="{MUTED}">{esc(line)}</text>'
            )
            y += 48
        y += 14

    # Bulleted list
    if bullets:
        for item in bullets:
            parts.append(f'  <circle cx="{pad + 9}" cy="{y - 11}" r="7" fill="{GOLD}"/>')
            parts.append(
                f'  <text x="{pad + 34}" y="{y}" font-family="{FONT}" font-size="34" '
                f'font-weight="500" fill="{WHITE}">{esc(item)}</text>'
            )
            y += 58

    # Optional pill call to action
    if cta:
        parts.append(
            f'  <rect x="{pad}" y="{h - 236}" width="{len(cta) * 21 + 76}" height="82" '
            f'rx="41" fill="{GOLD}"/>'
        )
        parts.append(
            f'  <text x="{pad + 38}" y="{h - 182}" font-family="{FONT}" font-size="33" '
            f'font-weight="700" fill="{INK}">{esc(cta)}</text>'
        )

    # Footer
    parts.append(
        f'  <line x1="{pad}" y1="{h - 118}" x2="{w - pad}" y2="{h - 118}" '
        f'stroke="{BLUE_SOFT}" stroke-width="1" opacity="0.22"/>'
    )
    parts.append(
        f'  <text x="{pad}" y="{h - 66}" font-family="{FONT}" font-size="29" '
        f'font-weight="600" fill="{BLUE_SOFT}">{esc(footer)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def build_story() -> str:
    """1080x1920 story template with an empty middle band for your own text."""
    w, h = 1080, 1920
    pad = 96
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="V&amp;P UkraLink story template">',
        "  <title>V&amp;P UkraLink — story template</title>",
        _defs(),
        _background(w, h),
        _mark((w - 132) / 2, 300, 132),
        f'  <text x="{w/2:.0f}" y="516" text-anchor="middle" font-family="{FONT}" '
        f'font-size="54" font-weight="700" letter-spacing="-1.4">'
        f'<tspan fill="{GOLD}">V&amp;P</tspan><tspan fill="{WHITE}" dx="11">UkraLink</tspan></text>',
        f'  <text x="{w/2:.0f}" y="566" text-anchor="middle" font-family="{FONT}" '
        f'font-size="23" font-weight="500" letter-spacing="3.4" fill="{BLUE_SOFT}">'
        f'UKRAINE VISA CONSULTANTS</text>',
        # Guide box showing the safe area for your own headline
        f'  <rect x="{pad}" y="760" width="{w - pad*2}" height="560" rx="28" '
        f'fill="{WHITE}" opacity="0.035" stroke="{BLUE_SOFT}" stroke-opacity="0.2" '
        f'stroke-width="2" stroke-dasharray="14 12"/>',
        f'  <text x="{w/2:.0f}" y="1050" text-anchor="middle" font-family="{FONT}" '
        f'font-size="34" font-weight="500" fill="{MUTED}">Add your headline here</text>',
        f'  <text x="{w/2:.0f}" y="1100" text-anchor="middle" font-family="{FONT}" '
        f'font-size="26" font-weight="400" fill="{MUTED}" opacity="0.7">'
        f'(this dashed box is a guide — delete it)</text>',
        f'  <text x="{w/2:.0f}" y="1700" text-anchor="middle" font-family="{FONT}" '
        f'font-size="31" font-weight="700" fill="{GOLD}">Book a consultation</text>',
        f'  <text x="{w/2:.0f}" y="1752" text-anchor="middle" font-family="{FONT}" '
        f'font-size="28" font-weight="500" fill="{BLUE_SOFT}">{esc(SITE)}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


POSTS = [
    {
        "slug": "01-intro",
        "eyebrow": "Ukraine visa specialists",
        "headline": ["Your route to", "Ukraine, mapped", "out properly."],
        "body": [
            "Short-stay, student, work, business,",
            "family or residence — we tell you which",
            "visa you actually need, and what it takes.",
        ],
        "cta": "Book a consultation",
    },
    {
        "slug": "02-visa-types",
        "eyebrow": "What we handle",
        "headline": ["Every Ukraine", "visa route"],
        "bullets": [
            "Short-stay visa (Type C)",
            "Long-stay visa (Type D)",
            "Student & university placement",
            "Work permit & employment",
            "Business & investor route",
            "Family reunification",
        ],
    },
    {
        "slug": "03-student",
        "eyebrow": "Student route",
        "headline": ["Studying in", "Ukraine?"],
        "bullets": [
            "University accreditation verified first",
            "Official invitation obtained for you",
            "Certificates legalised & translated",
            "Residence permit after you arrive",
        ],
        "cta": "Check your eligibility",
    },
    {
        "slug": "04-work",
        "eyebrow": "Work permit",
        "headline": ["Job offer in", "Ukraine?"],
        "body": [
            "Your employer must obtain an employment",
            "permit before you can apply for the visa.",
            "We deal with them directly, so you only",
            "have to sign things.",
        ],
        "cta": "Talk to a consultant",
    },
    {
        "slug": "05-refusal",
        "eyebrow": "Refusal review",
        "headline": ["Been refused", "before?"],
        "body": [
            "A refusal is usually a fixable gap in the",
            "evidence, not a permanent bar. We find",
            "the real reason, then decide between an",
            "appeal and a corrected re-application.",
        ],
        "cta": "Get your case reviewed",
    },
    {
        "slug": "06-book",
        "eyebrow": "Book a consultation",
        "headline": ["Pick a time", "that suits you"],
        "bullets": [
            "By video call or phone",
            "11:00 – 18:00 IST, Mon to Fri",
            "Fees quoted on the call",
            "Written checklist for your case",
        ],
        "footer": f"{SITE}  ·  {EMAIL}",
    },
]


def build_export_html(assets: list[tuple[str, str]]) -> str:
    """
    A self-contained page that turns each SVG into a downloadable PNG.

    The SVG source is embedded rather than fetched, because browsers block
    fetch() over file:// — this way the page works by double-clicking it, with
    no server and no image tooling installed.
    """
    blocks = []
    for name, svg in assets:
        root_w = int(svg.split('width="', 1)[1].split('"', 1)[0])
        root_h = int(svg.split('height="', 1)[1].split('"', 1)[0])
        blocks.append(
            f'<article class="card">\n'
            f'  <div class="preview">{svg}</div>\n'
            f'  <div class="meta">\n'
            f'    <div><strong>{esc(name)}</strong><small>{root_w} x {root_h}</small></div>\n'
            f'    <button data-name="{esc(name)}" data-w="{root_w}" data-h="{root_h}">'
            f'Download PNG</button>\n'
            f'  </div>\n'
            f'  <script type="text/plain" class="src">{svg}</script>\n'
            f'</article>'
        )
    cards = "\n".join(blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V&amp;P UkraLink — brand asset exporter</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:32px clamp(16px,4vw,48px) 80px; background:{INK};
         color:#e8eefb; font-family:{FONT}; }}
  h1 {{ font-size:clamp(22px,3vw,30px); margin:0 0 6px; letter-spacing:-0.5px; }}
  p.lede {{ color:{MUTED}; margin:0 0 26px; font-size:15px; max-width:70ch;
            line-height:1.6; }}
  .bar {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center;
          margin-bottom:30px; padding:16px 18px; border:1px solid rgba(143,186,255,.2);
          border-radius:14px; background:rgba(143,186,255,.05); }}
  label {{ font-size:14px; color:{MUTED}; }}
  select, button {{ font:inherit; }}
  select {{ padding:9px 12px; border-radius:9px; border:1px solid rgba(143,186,255,.28);
            background:#0f2550; color:#e8eefb; }}
  button {{ padding:10px 18px; border:0; border-radius:999px; cursor:pointer;
            background:{GOLD}; color:{INK}; font-weight:700; font-size:14px;
            transition:transform .15s, box-shadow .15s; }}
  button:hover {{ transform:translateY(-1px); box-shadow:0 8px 20px rgba(255,215,0,.24); }}
  button.ghost {{ background:transparent; color:#e8eefb;
                  border:1px solid rgba(143,186,255,.34); }}
  .grid {{ display:grid; gap:22px;
           grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); }}
  .card {{ border:1px solid rgba(143,186,255,.18); border-radius:16px;
           overflow:hidden; background:#0b1c3d; }}
  .preview {{ display:grid; place-items:center; padding:14px;
              background:repeating-conic-gradient(#12203c 0% 25%, #0d1830 0% 50%)
              50%/18px 18px; }}
  .preview svg {{ width:100%; height:auto; display:block; border-radius:6px;
                  box-shadow:0 6px 20px rgba(0,0,0,.4); }}
  .meta {{ display:flex; align-items:center; justify-content:space-between;
           gap:12px; padding:13px 15px; border-top:1px solid rgba(143,186,255,.14); }}
  .meta strong {{ display:block; font-size:14px; }}
  .meta small {{ color:{MUTED}; font-size:12px; }}
  #log {{ margin-top:22px; font-size:13px; color:{MUTED}; min-height:20px; }}
</style>
</head>
<body>

<h1>V&amp;P UkraLink — brand asset exporter</h1>
<p class="lede">
  Everything below is a vector file. Pick a size, then download the ones you
  want as PNG — Instagram accepts PNG directly. Nothing is uploaded anywhere;
  the conversion happens in this browser tab.
</p>

<div class="bar">
  <label for="scale">Export size</label>
  <select id="scale">
    <option value="1">1x — 1080px (Instagram standard)</option>
    <option value="2" selected>2x — 2160px (sharper, recommended)</option>
    <option value="3">3x — 3240px (print)</option>
  </select>
  <button id="all">Download all</button>
  <button class="ghost" id="allJpg">Download all as JPG</button>
</div>

<div class="grid">
{cards}
</div>

<div id="log"></div>

<script>
(function () {{
  const log = document.getElementById('log');
  const scaleSel = document.getElementById('scale');

  function render(svgText, w, h, scale, mime) {{
    return new Promise(function (resolve, reject) {{
      const blob = new Blob([svgText], {{ type: 'image/svg+xml;charset=utf-8' }});
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = function () {{
        const canvas = document.createElement('canvas');
        canvas.width = w * scale;
        canvas.height = h * scale;
        const ctx = canvas.getContext('2d');
        // JPG has no alpha, so lay down the brand background first.
        if (mime === 'image/jpeg') {{
          ctx.fillStyle = '{INK}';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }}
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob(function (out) {{
          out ? resolve(out) : reject(new Error('encode failed'));
        }}, mime, 0.94);
      }};
      img.onerror = function () {{
        URL.revokeObjectURL(url);
        reject(new Error('could not rasterise the SVG'));
      }};
      img.src = url;
    }});
  }}

  function save(blob, filename) {{
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {{ URL.revokeObjectURL(a.href); a.remove(); }}, 1000);
  }}

  async function exportCard(card, mime) {{
    const button = card.querySelector('button');
    const svgText = card.querySelector('script.src').textContent;
    const name = button.dataset.name;
    const w = +button.dataset.w, h = +button.dataset.h;
    const scale = +scaleSel.value;
    const ext = mime === 'image/jpeg' ? 'jpg' : 'png';
    const blob = await render(svgText, w, h, scale, mime);
    save(blob, name + '@' + scale + 'x.' + ext);
    return name;
  }}

  document.querySelectorAll('.card button').forEach(function (button) {{
    button.addEventListener('click', async function () {{
      const card = button.closest('.card');
      const original = button.textContent;
      button.textContent = 'Rendering...';
      button.disabled = true;
      try {{
        const name = await exportCard(card, 'image/png');
        log.textContent = 'Saved ' + name + '.';
      }} catch (err) {{
        log.textContent = 'Failed: ' + err.message;
      }}
      button.textContent = original;
      button.disabled = false;
    }});
  }});

  async function downloadAll(mime) {{
    const cards = Array.from(document.querySelectorAll('.card'));
    for (let i = 0; i < cards.length; i++) {{
      log.textContent = 'Rendering ' + (i + 1) + ' of ' + cards.length + '...';
      try {{
        await exportCard(cards[i], mime);
      }} catch (err) {{
        log.textContent = 'Failed on file ' + (i + 1) + ': ' + err.message;
        return;
      }}
      // Browsers throttle rapid successive downloads.
      await new Promise(function (r) {{ setTimeout(r, 420); }});
    }}
    log.textContent = 'Done — saved ' + cards.length + ' files to your downloads folder.';
  }}

  document.getElementById('all').addEventListener('click', function () {{
    downloadAll('image/png');
  }});
  document.getElementById('allJpg').addEventListener('click', function () {{
    downloadAll('image/jpeg');
  }});
}})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Job vacancy carousels
# --------------------------------------------------------------------------- #
# Everything below is taken from the employer briefs as supplied. Only the
# salary figures differ: both ranges carry a 20% uplift, applied on request.
#   Greenhouse  $500-$650  ->  $600-$780
#   Bakery      $450-$600  ->  $540-$720
# Nothing else has been added or embellished — if a benefit is not in the brief,
# it is not on the post.

JOBS = [
    {
        "slug": "greenhouse",
        "title": ["Greenhouse", "Agriculture Worker"],
        "subtitle": "Ukraine · Modern vegetable cultivation complexes",
        "salary": "$600 – $780",
        "salary_note": "USD per month, depending on hours and output",
        "provides": [
            "Official employment contract",
            "Free housing with all utilities",
            "Free transport to the complex",
            "Harvesting performance bonus",
            "Full legalization support",
        ],
        "duties": [
            "Planting & crop care",
            "Harvesting vegetables",
            "Packaging & sorting produce",
            "Pruning & vine maintenance",
        ],
        "conditions": [
            ("Working hours", "200 – 220 hrs / month"),
            ("Schedule", "6 days / week, day shifts"),
            ("Age limit", "Men & women up to 52"),
            ("Experience", "Agricultural experience is a plus"),
        ],
    },
    {
        "slug": "bakery",
        "title": ["Bakery", "Production Worker"],
        "subtitle": "Ukraine · Major industrial bakery facility",
        "salary": "$540 – $720",
        "salary_note": "USD per month, paid on a regular monthly schedule",
        "provides": [
            "Official full-time contract",
            "Free accommodation near the site",
            "Free daily meals on shift",
            "Work uniform & safety gear",
            "On-site coordinator support",
            "Full legalization support",
        ],
        "duties": [
            "Operate the dough moulding line",
            "Package finished bakery goods",
            "Monitor oven baking cycles",
            "Clean & sanitise equipment",
        ],
        "conditions": [
            ("Working hours", "210 – 240 hrs / month"),
            ("Schedule", "5 – 6 working days / week"),
            ("Age limit", "Men & women up to 50"),
            ("Experience", "No experience required"),
        ],
    },
]


def _shell(w: int, h: int, label: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(label)}">\n'
        f"  <title>{esc(label)}</title>\n{_defs()}\n{_background(w, h)}\n{body}\n</svg>\n"
    )


def _pill(x: int, y: int, text: str, size: int = 25) -> str:
    width = int(len(text) * (size * 0.72)) + 56
    return (
        f'  <rect x="{x}" y="{y}" width="{width}" height="56" rx="28" fill="{GOLD}"/>\n'
        f'  <text x="{x + 28}" y="{y + 38}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="700" letter-spacing="3" fill="{INK}">{esc(text.upper())}</text>'
    )


def build_job_hero(job: dict) -> str:
    pad = 88
    p = [_lockup(pad, 74), _pill(pad, 214, "Now hiring")]

    y = 392
    for line in job["title"]:
        size = 76 if len(line) <= 19 else 64
        p.append(
            f'  <text x="{pad}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="700" letter-spacing="-2" fill="{WHITE}">{esc(line)}</text>'
        )
        y += 88
    p.append(
        f'  <text x="{pad}" y="{y + 22}" font-family="{FONT}" font-size="30" '
        f'font-weight="500" fill="{BLUE_SOFT}">{esc(job["subtitle"])}</text>'
    )

    # Salary is the hook, so it gets its own framed block.
    card_y = 624
    p.append(
        f'  <rect x="{pad}" y="{card_y}" width="{1080 - pad*2}" height="186" rx="26" '
        f'fill="{WHITE}" fill-opacity="0.06" stroke="{GOLD}" stroke-opacity="0.34" '
        f'stroke-width="2"/>'
    )
    p.append(
        f'  <text x="{pad + 38}" y="{card_y + 54}" font-family="{FONT}" font-size="24" '
        f'font-weight="700" letter-spacing="3.4" fill="{GOLD}">MONTHLY SALARY</text>'
    )
    p.append(
        f'  <text x="{pad + 38}" y="{card_y + 132}" font-family="{FONT}" font-size="72" '
        f'font-weight="700" letter-spacing="-1.6" fill="{WHITE}">{esc(job["salary"])}</text>'
    )
    p.append(
        f'  <text x="{pad + 38}" y="{card_y + 168}" font-family="{FONT}" font-size="23" '
        f'font-weight="400" fill="{MUTED}">{esc(job["salary_note"])}</text>'
    )

    p.append(
        f'  <text x="{pad}" y="898" font-family="{FONT}" font-size="29" '
        f'font-weight="700" fill="{GOLD}">Swipe for full details &#8594;</text>'
    )
    p.append(
        f'  <line x1="{pad}" y1="962" x2="{1080 - pad}" y2="962" stroke="{BLUE_SOFT}" '
        f'stroke-width="1" opacity="0.22"/>'
    )
    p.append(
        f'  <text x="{pad}" y="1014" font-family="{FONT}" font-size="28" '
        f'font-weight="600" fill="{BLUE_SOFT}">{esc(SITE)}</text>'
    )
    return _shell(1080, 1080, " ".join(job["title"]) + " — vacancy", "\n".join(p))


def build_job_details(job: dict) -> str:
    pad = 88
    p = [_lockup(pad, 74)]

    def section(heading: str, items: list[str], y: int) -> int:
        p.append(
            f'  <text x="{pad}" y="{y}" font-family="{FONT}" font-size="28" '
            f'font-weight="700" letter-spacing="3.4" fill="{GOLD}">{esc(heading.upper())}</text>'
        )
        p.append(f'  <rect x="{pad}" y="{y + 18}" width="62" height="3" rx="2" fill="{GOLD}"/>')
        y += 74
        for item in items:
            p.append(f'  <circle cx="{pad + 8}" cy="{y - 10}" r="6" fill="{GOLD}"/>')
            p.append(
                f'  <text x="{pad + 30}" y="{y}" font-family="{FONT}" font-size="30" '
                f'font-weight="500" fill="{WHITE}">{esc(item)}</text>'
            )
            y += 52
        return y

    y = section("What we provide", job["provides"], 236)
    section("Job duties", job["duties"], y + 44)

    p.append(
        f'  <line x1="{pad}" y1="962" x2="{1080 - pad}" y2="962" stroke="{BLUE_SOFT}" '
        f'stroke-width="1" opacity="0.22"/>'
    )
    p.append(
        f'  <text x="{pad}" y="1014" font-family="{FONT}" font-size="28" '
        f'font-weight="600" fill="{BLUE_SOFT}">{esc(SITE)}</text>'
    )
    return _shell(1080, 1080, " ".join(job["title"]) + " — what we provide",
                  "\n".join(p))


def build_job_conditions(job: dict) -> str:
    pad = 88
    p = [_lockup(pad, 74)]
    p.append(
        f'  <text x="{pad}" y="238" font-family="{FONT}" font-size="28" '
        f'font-weight="700" letter-spacing="3.4" fill="{GOLD}">CONDITIONS</text>'
    )
    p.append(f'  <rect x="{pad}" y="256" width="62" height="3" rx="2" fill="{GOLD}"/>')

    y = 336
    for label, value in job["conditions"]:
        p.append(
            f'  <text x="{pad}" y="{y}" font-family="{FONT}" font-size="24" '
            f'font-weight="600" letter-spacing="2.4" fill="{BLUE_SOFT}">'
            f'{esc(label.upper())}</text>'
        )
        size = 34 if len(value) <= 34 else 29
        p.append(
            f'  <text x="{pad}" y="{y + 44}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="600" fill="{WHITE}">{esc(value)}</text>'
        )
        y += 112

    p.append(_pill(pad, 800, "Apply now", 27))
    p.append(
        f'  <text x="{pad}" y="922" font-family="{FONT}" font-size="27" '
        f'font-weight="500" fill="{MUTED}">Send your CV to {esc(EMAIL)}</text>'
    )
    p.append(
        f'  <line x1="{pad}" y1="962" x2="{1080 - pad}" y2="962" stroke="{BLUE_SOFT}" '
        f'stroke-width="1" opacity="0.22"/>'
    )
    p.append(
        f'  <text x="{pad}" y="1014" font-family="{FONT}" font-size="28" '
        f'font-weight="600" fill="{BLUE_SOFT}">{esc(SITE)}</text>'
    )
    return _shell(1080, 1080, " ".join(job["title"]) + " — conditions", "\n".join(p))


def build_vacancy_teaser() -> str:
    """Single feed post announcing both roles at once."""
    pad = 88
    p = [_lockup(pad, 74), _pill(pad, 214, "Vacancies in Ukraine")]
    p.append(
        f'  <text x="{pad}" y="392" font-family="{FONT}" font-size="76" '
        f'font-weight="700" letter-spacing="-2" fill="{WHITE}">Two roles open</text>'
    )

    y = 470
    for job in JOBS:
        p.append(
            f'  <rect x="{pad}" y="{y}" width="{1080 - pad*2}" height="176" rx="24" '
            f'fill="{WHITE}" fill-opacity="0.06" stroke="{BLUE_SOFT}" '
            f'stroke-opacity="0.2" stroke-width="2"/>'
        )
        p.append(
            f'  <text x="{pad + 34}" y="{y + 62}" font-family="{FONT}" font-size="38" '
            f'font-weight="700" fill="{WHITE}">{esc(" ".join(job["title"]))}</text>'
        )
        p.append(
            f'  <text x="{pad + 34}" y="{y + 114}" font-family="{FONT}" font-size="44" '
            f'font-weight="700" fill="{GOLD}">{esc(job["salary"])}</text>'
        )
        p.append(
            f'  <text x="{pad + 34}" y="{y + 150}" font-family="{FONT}" font-size="24" '
            f'font-weight="400" fill="{MUTED}">USD / month · official contract · '
            f'housing provided</text>'
        )
        y += 204

    p.append(
        f'  <text x="{pad}" y="{y + 44}" font-family="{FONT}" font-size="28" '
        f'font-weight="600" fill="{BLUE_SOFT}">Send your CV to {esc(EMAIL)}</text>'
    )
    p.append(
        f'  <line x1="{pad}" y1="962" x2="{1080 - pad}" y2="962" stroke="{BLUE_SOFT}" '
        f'stroke-width="1" opacity="0.22"/>'
    )
    p.append(
        f'  <text x="{pad}" y="1014" font-family="{FONT}" font-size="28" '
        f'font-weight="600" fill="{BLUE_SOFT}">{esc(SITE)}</text>'
    )
    return _shell(1080, 1080, "Two vacancies open in Ukraine", "\n".join(p))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for post in POSTS:
        path = OUT / f"{post['slug']}.svg"
        path.write_text(build_post(**post), encoding="utf-8")
        written.append(path)
    story = OUT / "story-template.svg"
    story.write_text(build_story(), encoding="utf-8")
    written.append(story)

    # Job vacancies live in their own folder: they expire, the brand posts do not.
    jobs_dir = OUT / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    teaser = jobs_dir / "00-both-vacancies.svg"
    teaser.write_text(build_vacancy_teaser(), encoding="utf-8")
    written.append(teaser)
    for job in JOBS:
        slides = [
            ("1-hero", build_job_hero(job)),
            ("2-details", build_job_details(job)),
            ("3-conditions", build_job_conditions(job)),
        ]
        for suffix, svg in slides:
            path = jobs_dir / f"{job['slug']}-{suffix}.svg"
            path.write_text(svg, encoding="utf-8")
            written.append(path)

    # Build the exporter over the posts plus the hand-written logo files.
    logo_dir = Path(__file__).parent / "logo"
    assets: list[tuple[str, str]] = []
    for path in written:
        assets.append((path.stem, path.read_text(encoding="utf-8")))
    for name in ("logo-stacked", "logo-horizontal", "logo-icon",
                 "logo-mono-light", "logo-mono-dark"):
        candidate = logo_dir / f"{name}.svg"
        if candidate.is_file():
            assets.append((name, candidate.read_text(encoding="utf-8")))

    export = Path(__file__).parent / "export.html"
    export.write_text(build_export_html(assets), encoding="utf-8")
    written.append(export)

    for path in written:
        print(f"  wrote {path.relative_to(Path(__file__).parent.parent)} "
              f"({path.stat().st_size:,} bytes)")
    print(f"\n{len(written)} files generated ({len(assets)} assets in the exporter).")


if __name__ == "__main__":
    main()
