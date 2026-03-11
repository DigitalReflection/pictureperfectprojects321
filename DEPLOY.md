# Deploying to Cloudflare Pages

This project is a plain static site. There is no build step.

## Build settings
- Build command: leave blank
- Output directory: `.`
- Framework preset: None

## Route setup
- `/` serves the main landing page directly from `index.html`
- `/discountoffer/` serves the same landing page from `discountoffer/index.html`
- `/thank-you/` serves the form confirmation page from `thank-you/index.html`

This avoids redirect loops and works cleanly with Cloudflare Pages static hosting.

## Deployment steps
1) Push this repo to GitHub.
2) In Cloudflare Pages, create a project and connect the repo.
3) Use these settings:
   - Framework preset: None
   - Build command: leave blank
   - Build output directory: `.`
4) Deploy the site.
5) In the Pages project, open **Custom domains** and add:
   - `pictureperfectprojects321.com`
   - `www.pictureperfectprojects321.com` (optional, but recommended)
6) Let Cloudflare create the DNS records automatically. If you must do it manually:
   - Remove old A/AAAA records for the root and `www`
   - Create CNAME `@` -> your Pages hostname
   - Create CNAME `www` -> your Pages hostname
   - Leave the orange cloud proxy enabled
7) In **SSL/TLS**, set the mode to **Full**. After the edge certificate shows **Active**, you can switch to **Full (strict)**.

## Test after deploy
- `https://www.pictureperfectprojects321.com/` should load the landing page
- `https://www.pictureperfectprojects321.com/discountoffer/` should load the same offer page
- `https://www.pictureperfectprojects321.com/thank-you/` should load the thank-you page
- Submit the quote form and confirm Formspree redirects to `/thank-you/`

## Automated Cloudflare audit / repair
You can audit the public DNS and HTTPS state with:

```powershell
python scripts/cloudflare_domain_repair.py audit
```

To let the script clean up bad DNS records and re-attach the custom domains to Cloudflare Pages, set:

```powershell
$env:CF_API_TOKEN="your-token"
$env:CF_ACCOUNT_ID="your-account-id"
$env:CF_PAGES_PROJECT_NAME="pictureperfectprojects321"
python scripts/cloudflare_domain_repair.py fix --ssl-mode full
```

The script will:
- remove known bad Namecheap parking records
- detect whether this repo is using Cloudflare Pages or a Worker/static-assets deploy
- ensure the apex domain and `www` are attached to the Pages project when running in Pages mode
- optionally set the zone SSL mode
- re-check public DNS and HTTPS at the end

## Local preview (optional)
Run:

```powershell
python -m http.server 4173
```

Then visit:
- `http://localhost:4173/`
- `http://localhost:4173/discountoffer/`
- `http://localhost:4173/thank-you/`
