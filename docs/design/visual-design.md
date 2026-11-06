# VPS visual design: "Night Drive"

The look combines Apple's product pages with the GTA VI site. Apple supplies the
restraint: big tight headlines, a quiet type scale, generous space, frosted glass and
soft easing. GTA VI supplies the mood: a deep indigo night, a sunset gradient from
peach into pink and violet, lavender text accents, and pill-shaped controls.

The tokens below were measured from the computed styles of apple.com/iphone and
rockstargames.com/VI (6 November 2026). They are used as inspiration. We do not copy
either site's assets, logos, images or fonts. SF Pro and Rockstar's typefaces are
proprietary, so we self-host Inter and Inter Tight (SIL Open Font License) instead.

## Rules that do not bend

1. **Restyle only.** Every page keeps its text, form fields, field names, ids, URLs,
   HTMX attributes and existing CSS class names. You may add elements, classes and
   wrappers, and you may add new decorative or introductory text on the sign-in and
   registration pages. You may not remove or reword existing text, since the tests
   assert it.
2. **WCAG 2.1 AA.** Text contrast is at least 4.5:1, or 3:1 for large text, against
   whatever is actually behind it, gradients and glass included. Every interactive
   control has a visible `:focus-visible` style. Touch targets are at least 44px tall.
   axe-core must still report 0 violations.
3. **Motion is optional.** All animation and transitions sit behind
   `@media (prefers-reduced-motion: no-preference)`, or are switched off under
   `prefers-reduced-motion: reduce`.
4. **No frameworks.** Plain CSS, no Tailwind or Bootstrap, and no new JavaScript
   except HTMX, which is already there. No external requests apart from the existing
   HTMX script: fonts are served from `static/fonts/`.
5. **Mobile first.** Every page works at 375px wide with no horizontal page scroll.
   Wide tables scroll inside their own container.

## Tokens

```css
:root {
  color-scheme: dark;

  /* Night (GTA VI) */
  --bg:            #07080f;   /* page */
  --bg-2:          #0c0d1b;
  --surface:       rgba(22, 23, 46, 0.62);   /* glass card */
  --surface-solid: #12132a;
  --surface-2:     #1a1b36;   /* raised: inputs, table header */
  --border:        rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.16);

  /* Text (Apple dark mode) */
  --text:   #f5f5f7;
  --text-2: #c7c7d1;   /* secondary */
  --text-3: #9a9ab0;   /* tertiary, still at least 4.5:1 on --bg */
  --lavender: #ccc2f5; /* eyebrows and accents (GTA VI) */
  --link:   #6cb6ff;

  /* Sunset accent (GTA VI) */
  --peach:  #fec497;
  --pink:   #f6879e;
  --rose:   #e9639b;
  --violet: #9f87c8;
  --sunset: linear-gradient(120deg, #fec497 0%, #f6879e 40%, #e9639b 68%, #9f87c8 100%);
  --on-sunset: #120a14;  /* dark text on sunset buttons */

  /* Status (Apple system colours, dark) */
  --green:  #30d158;
  --yellow: #ffd60a;
  --red:    #ff6961;
  --blue:   #64d2ff;
  --grey:   #8e8e9a;

  /* Shape */
  --radius-card: 28px;   /* Apple tiles */
  --radius-field: 14px;
  --radius-pill: 980px;  /* Apple and GTA VI pills */

  /* Glass */
  --glass: saturate(180%) blur(20px);  /* Apple nav */

  /* Motion (Apple) */
  --ease: cubic-bezier(0.4, 0, 0.6, 1);
  --ease-out: cubic-bezier(0, 0, 0.5, 1);
  --fast: 180ms;
  --slow: 600ms;
}
```

## Type

- Body: `Inter`, 17px, line-height 1.47, weight 400, colour `--text`. Use
  `font-feature-settings: "cv11", "ss01"` and `tabular-nums` on numbers in tables and
  stat tiles.
- Display: `Inter Tight`, weight 650 to 700, letter-spacing −0.02em to −0.035em
  (tighter as the size grows).
- Scale, from Apple's measured steps of 80, 56, 48, 28, 24, 17 and 12px:
  - hero: `clamp(3rem, 8vw, 6rem)`
  - h1: `clamp(2.25rem, 4.5vw, 3.5rem)`
  - h2: `clamp(1.5rem, 2.5vw, 1.75rem)`
  - h3: 1.3rem
  - small: 0.875rem
  - eyebrow: 0.75rem, uppercase, letter-spacing 0.14em, `--lavender`
- Headline highlight: words wrapped in `.gradient-text` get the sunset gradient
  through `background-clip: text`. Only use this at 24px and above, and check the
  contrast of the darkest stop (`--violet` on `--bg` passes).

## Page frame

- **Background.** `--bg`, with a fixed layered glow behind everything: a large rose
  radial at the top centre (about 22% alpha), a violet radial at the bottom left and a
  faint peach radial at the right. It should feel like a city at dusk, and it must stay
  subtle enough that text contrast holds.
- **Header and navigation.** Sticky, with a glass background (`rgba(7, 8, 15, 0.72)`
  plus `--glass`) and a hairline bottom border. The brand wordmark sits on the left with
  a small sunset-gradient mark. Nav links are 14px, `--text-2`, turning `--text` on
  hover. The current page's link gets a soft pill highlight; compare `request.path` in
  the template. The admin nav has 12 links, so on small screens it becomes a single
  horizontally scrollable row and never a tall stack. The user email and role chip sit
  on the right with a ghost-pill "Sign out" button.
  - Keep `<nav class="site-nav"` exactly; a test asserts it.
- **Main.** `max-width: 75rem`, centred, side padding `clamp(1rem, 4vw, 2.5rem)`. Each
  page starts with a header block: an optional eyebrow, the h1, and an intro paragraph
  in `--text-2`.
- **Entry motion.** Main content fades up 12px with a short stagger (600ms,
  `--ease-out`), behind reduced-motion as above.

## Components

All of these live in `static/css/vps.css`. Map every existing class onto them.

- **Card** (`.card`, plus the existing `*-card`, `*-panel` and `*-section` classes):
  `--surface` background, `--glass` backdrop, 1px `--border`, `--radius-card`, padding
  `clamp(1.25rem, 3vw, 2rem)`, and a faint inner top highlight
  (`inset 0 1px 0 rgba(255, 255, 255, 0.06)`).
- **Buttons.**
  - Primary (submit buttons and the existing primary classes): sunset gradient,
    `--on-sunset` text, weight 600, pill shape, 44px minimum height, `0 8px 30px` rose
    glow on hover with a 1px lift, and pressed state `scale(0.98)`.
  - Secondary or ghost: transparent, `--border-strong`, `--text`, pill.
  - Danger: transparent with `--red` text and border.
  - Disabled: 40% opacity, with no glow.
- **Fields.** Labels are 14px, weight 600, `--text-2`. Inputs and selects use
  `--surface-2`, 1px `--border-strong`, `--radius-field`, at least 48px tall and 16px
  text so iOS does not zoom. Focus: border `--pink` plus a
  `0 0 0 4px rgba(246, 135, 158, 0.28)` ring. Error text uses `--red`. Native date
  pickers inherit the dark `color-scheme`.
- **Tables.** Wrap them in a card that scrolls horizontally. Headers are 12px,
  uppercase, letter-spaced and `--text-3`, on `--surface-2`. Rows have hairline
  dividers and a hover tint of `rgba(255, 255, 255, 0.03)`. Numbers are right-aligned
  with tabular figures.
- **Stat tile** (`.stat`): big Inter Tight number (`clamp(2rem, 4vw, 3rem)`) above a
  small label. Coloured variants: free green, reserved yellow, occupied red, blocked
  grey. Use these on live occupancy, the reports and any count.
- **Chips and badges** (states such as Reserved, Active, Completed, Cancelled, Expired,
  Waived, and the user's role): pill, 12 to 13px, weight 600, tinted background at 16%
  alpha of the state colour, with the state colour as text. Check contrast on each one.
- **Messages** (`.message-success`, `-error`, `-warning`, `-info`): glass card with a
  4px left bar in the state colour, and text in `--text`.
- **Progress or distribution bar** (occupancy): 10px tall, rounded, segments in the
  status colours, with a soft glow.
- **Empty states:** centred, `--text-3`, with an optional thin-line icon drawn in CSS.

## The sign-in page (the first impression)

This is the page a new visitor sees first, so it carries the "breathtaking" moment.

- **Layout.** Full viewport, split into two columns from 900px up. The left column is
  the hero; the right column holds the glass sign-in card. Below 900px they stack, hero
  first and compact.
- **Hero.**
  - Eyebrow: "Vehicle Parking System".
  - Headline in hero size: "Park" on one line, then "before you arrive." in
    `.gradient-text`.
  - One-sentence subline in `--text-2`: "Find a slot, book it in seconds, and drive
    straight in."
  - Three small glass feature pills: "Live availability", "Race-safe booking" and
    "Pay at the gate".
- **Atmosphere.** Behind the hero, a slowly drifting aurora of two or three blurred
  sunset-coloured blobs (CSS only, 20 to 30 second loops), with a horizon line of thin
  perspective grid lines fading out. Everything is decorative (`aria-hidden="true"`),
  and the animation stops under reduced motion.
- **Card.** The existing form and its text, restyled: glass, the largest radius, a
  sunset primary button across the full width, and the links below it.
- Give `password_reset_*` and `register.html` the same backdrop and glass card, without
  the full hero copy. The register page may use a shorter hero ("Join in a minute.").

## Page-specific direction

- **Find parking and the search result.** The form goes in a glass card. The result
  panel becomes a hero-like card: a huge slot count, the forecast as a percentage stat
  with a Low, Medium or High chip, and the "Book a slot" button as primary.
- **Live occupancy.** One card per lot. Four stat tiles in a row (2×2 on mobile), the
  distribution bar, then the slot-type table. The live indicator is a pulsing green dot
  behind reduced motion.
- **Gate console.** Check-in, check-out and walk-in as three large glass panels. Make
  the reference inputs big (20px text, 56px tall) so they are scanner friendly, with a
  primary button in each.
- **My bookings.** A card with a list of bookings, a state chip on each, and charges
  shown as a chip or amount.
- **Reports and audit.** The filter form sits in a compact inline glass toolbar above
  the table card. "Download CSV" is a secondary pill.
- **Receipts** (`gate/receipt.html`, `billing/receipt.html`): these also print, so
  under `@media print` everything turns black on white with no backgrounds, glass or
  navigation.

## Files

- `static/css/vps.css`: tokens, base styles, components, and every class that
  currently lives in the `<style>` blocks.
- `static/css/pages/*.css` (optional): page-specific additions, linked through a
  `{% block extra_css %}` in `base.html`.
- `static/fonts/InterVariable.woff2` and `static/fonts/InterTightVariable.woff2`, with
  `LICENSE-Inter.txt`.
- `base.html` loads the stylesheet with `{% load static %}` and
  `<link rel="stylesheet" href="{% static 'css/vps.css' %}">`, and preloads the two
  fonts. The `<style>` blocks in `base.html`, `lots/occupancy.html` and
  `lots/occupancy_table.html` move into the CSS files.
- Static files are served by WhiteNoise, so they work with `DEBUG` off and under
  Gunicorn.
