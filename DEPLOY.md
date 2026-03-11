# Deploying to Cloudflare Pages

This project is a static site (HTML/CSS/JS only). No build step is required.

## Build settings
- Build command: _None (leave blank)_
- Output directory: . (root of the repo)

## Files relevant to Pages
- _redirects — root redirect and SPA-style fallback for /discountoffer
- index.html — root redirect page
- discountoffer/index.html — primary landing page

## Deployment steps
1) Push this repo to your Git provider (GitHub/GitLab/Bitbucket).
2) In Cloudflare Pages, create a new project and connect this repo.
3) Set build command to **None** (blank) and output directory to **.**.
4) Deploy. Pages will publish the static files and apply _redirects.
5) Attach the custom domain:
   - In Pages project → **Custom domains** → **Set up a custom domain**.
   - Enter pictureperfectprojects321.com and follow DNS prompt. A CNAME to the Pages hostname will be suggested; create/update the DNS record in Cloudflare DNS.
   - Add the www subdomain if desired, CNAME to the same target.
6) Verify HTTPS has issued (usually within a few minutes).

## Test the redirect
- Open https://www.pictureperfectprojects321.com/ → should 302 to /discountoffer.
- Open https://www.pictureperfectprojects321.com/discountoffer → should load the landing page.
- Refresh while on /discountoffer to confirm it still loads (handled by _redirects).

## Local preview (optional)
- Serve locally with any static server: 
px serve . then visit http://localhost:3000/discountoffer.

## Notes
- Do not remove _redirects; it enforces the root → /discountoffer behavior and keeps nested routes working if you add more under /discountoffer.
