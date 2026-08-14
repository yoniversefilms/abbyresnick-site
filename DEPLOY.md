# Domain & email setup — abbyresnick.com

Registrar/DNS: **GoDaddy**. Site: **GitHub Pages** (`yoniversefilms/abbyresnick-site`).
Email: **Google Workspace** (`hello@abbyresnick.com`).

> **Order matters.** Add the DNS records FIRST, wait until they resolve, and only
> then set the custom domain in GitHub. Setting the custom domain early makes the
> `github.io` staging URL redirect to a domain that doesn't answer yet.

---

## Step 1 — Google Workspace signup
Buy direct at **workspace.google.com** (buying through GoDaddy is usually pricier).
Business Starter is **$7/user/month** on annual billing, $8.40 month-to-month.

During setup Google asks you to verify you own `abbyresnick.com` — it issues a
**TXT record** to add at GoDaddy. Then create the user `hello@abbyresnick.com`.

## Step 2 — DNS records at GoDaddy
GoDaddy → *My Products* → `abbyresnick.com` → **DNS** → *Manage DNS*.

### 2a. Delete first
These currently point the domain at GoDaddy's parking page and GoDaddy's mail:

| Type | Value to REMOVE |
|---|---|
| A | `13.248.243.5` |
| A | `76.223.105.230` |
| MX | `mailstore1.secureserver.net` (priority 10) |
| MX | `smtp.secureserver.net` (priority 0) |

Also turn off any **Domain Forwarding / parking** on the domain.

### 2b. Website — GitHub Pages
| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `185.199.108.153` | 1 hr |
| A | `@` | `185.199.109.153` | 1 hr |
| A | `@` | `185.199.110.153` | 1 hr |
| A | `@` | `185.199.111.153` | 1 hr |
| AAAA | `@` | `2606:50c0:8000::153` | 1 hr |
| AAAA | `@` | `2606:50c0:8001::153` | 1 hr |
| AAAA | `@` | `2606:50c0:8002::153` | 1 hr |
| AAAA | `@` | `2606:50c0:8003::153` | 1 hr |
| CNAME | `www` | `yoniversefilms.github.io` | 1 hr |

### 2c. Email — Google Workspace
| Type | Name | Value | Priority |
|---|---|---|---|
| MX | `@` | `smtp.google.com` | 1 |
| TXT | `@` | *(the verification string Google gives you)* | — |
| TXT | `@` | `v=spf1 include:_spf.google.com ~all` | — |

**SPF matters** — it's what stops her mail to corporate planners and DMCs landing
in spam. Add it.

After mail is flowing, turn on **DKIM**: Workspace Admin → *Apps → Google Workspace
→ Gmail → Authenticate email* → generate the key → add the TXT record it gives you
→ click *Start authentication*. Do this; it's the other half of deliverability.

## Step 3 — Point GitHub at the domain
Once `dig +short abbyresnick.com` returns the four `185.199.*` addresses,
add a `CNAME` file to the repo root containing `abbyresnick.com`, then in the
repo: *Settings → Pages → Custom domain* → `abbyresnick.com` → **Enforce HTTPS**.

Certificate issuance takes a few minutes after DNS resolves.

## Step 4 — Update the forms
Both inquiry forms currently redirect to the staging thank-you page. Once the
domain is live, change `_next` in `index.html` and `corporate.html` to:
`https://abbyresnick.com/thank-you.html`

---

## Verify
```bash
dig +short abbyresnick.com          # expect the four 185.199.* addresses
dig +short MX abbyresnick.com       # expect: 1 smtp.google.com
dig +short TXT abbyresnick.com      # expect the SPF record
curl -sI https://abbyresnick.com | head -1   # expect HTTP/2 200
```
