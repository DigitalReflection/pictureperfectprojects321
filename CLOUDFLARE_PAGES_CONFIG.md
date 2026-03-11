# Cloudflare Pages settings

## Project type
- Static site

## Build configuration
- Framework preset: None
- Build command: leave blank
- Build output directory: `.`
- Root directory: leave blank

## Routes
- `/` -> `index.html`
- `/discountoffer/` -> `discountoffer/index.html`
- `/thank-you/` -> `thank-you/index.html`

No redirect rules are required for this setup.

## Custom domains
- Add `pictureperfectprojects321.com`
- Add `www.pictureperfectprojects321.com` if you want both hostnames live
- Point both hostnames to the Pages project hostname with proxied CNAME records

## SSL
- Start with SSL/TLS mode `Full`
- Switch to `Full (strict)` once the Pages edge certificate is active
- Do not use `Flexible`

## Form handling
- Form posts to Formspree: `https://formspree.io/f/xqeypwrj`
- Success redirect: `https://www.pictureperfectprojects321.com/thank-you/`

## Assets
- Logo loads from `https://i.imgur.com/tfSh82J.png`
- All remote assets use HTTPS
