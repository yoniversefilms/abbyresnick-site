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

## Forms
Both inquiry forms post to **FormSubmit** (no account, no backend):
`index.html` (#inquire) and `corporate.html` (#inquiry) → `abbyresnick@gmail.com`.
Hidden fields set the subject, redirect to `thank-you.html`, use a table email
template, disable the captcha, and include a `_honey` honeypot for spam.

> **Activation:** the first submission triggers a one-click confirmation email to
> the destination address. Nothing is delivered until that link is clicked.
>
> **Then harden it:** replace the address in both `action` URLs with the random
> alias FormSubmit issues, so the inbox is not exposed in public HTML.

## Open items before launch
- [ ] Activate FormSubmit (submit once, click the confirmation email)
- [ ] Swap form actions to the FormSubmit alias URL (hides the email address)
- [ ] Point `_next` at `https://abbyresnick.com/thank-you.html` when the domain is live
- [ ] Hi-res photography — current images are capped by low-res source files
- [ ] Real client testimonials (sections removed until permissioned quotes exist)
- [ ] Decide whether `hello@abbyresnick.com` forwards somewhere, or change the
      displayed address (it is shown on the site but may not receive mail yet)
- [ ] Confirm a public phone number and any published pricing
