# abbyresnick.com

Static marketing site for **Abby Resnick Floral Design** — a boutique floral and
event design studio in Los Angeles. Events only: weddings, private celebrations,
corporate and brand events, installations.

## Structure
| File | Purpose |
|---|---|
| `index.html` | Homepage |
| `corporate.html` | Corporate & brand events (planner / DMC facing) |
| `thank-you.html` | Form success redirect |
| `404.html` | Not-found page |
| `assets/brand/` | Logo (plum + reversed cream SVG) |
| `assets/events/`, `assets/corporate/` | Photography |

Self-contained HTML/CSS — no build step. Open `index.html` directly, or:
`python3 -m http.server 4321`

## Brand
Cormorant Garamond (display) + Jost (sans). Deep plum `#5A2A42`, warm cream
`#F5EFE2`, lavender `#B9A7D0`, champagne `#B0895A`.

## Deploy
GitHub Pages from `main`. Custom domain configured via `CNAME`.

## Open items before launch
- [ ] Contact form endpoint — replace `FORMSPREE_ID` in `corporate.html`
- [ ] Replace low-resolution photography with hi-res originals
- [ ] Real client testimonials (sections removed until permissioned quotes exist)
- [ ] Confirm public phone number and any published pricing
