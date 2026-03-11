#!/usr/bin/env python3
"""
Audit and optionally repair the Cloudflare Pages/domain setup for this site.

Public audit mode works without credentials.

Fix mode requires:
  - CF_API_TOKEN
  - CF_ACCOUNT_ID
  - CF_PAGES_PROJECT_NAME

Optional:
  - CF_ZONE_ID
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


API_BASE = "https://api.cloudflare.com/client/v4"
DNS_GOOGLE = "https://dns.google/resolve"


class CloudflareError(RuntimeError):
    pass


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


def pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def public_dns_lookup(name: str, record_type: str) -> Dict[str, Any]:
    query = urllib.parse.urlencode({"name": name, "type": record_type})
    url = f"{DNS_GOOGLE}?{query}"
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def http_head(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
            return {
                "url": url,
                "status": response.getcode(),
                "headers": dict(response.headers.items()),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "final_url": exc.geturl(),
        }
    except Exception as exc:  # pragma: no cover - network edge cases
        return {
            "url": url,
            "error": str(exc),
        }


@dataclass
class CloudflareClient:
    api_token: str

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{API_BASE}{path}"
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"

        body = None
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                raise CloudflareError(f"{method} {path} failed: HTTP {exc.code}: {raw}") from exc
            raise CloudflareError(f"{method} {path} failed: {pretty(parsed)}") from exc

        parsed = json.loads(raw)
        if not parsed.get("success", False):
            raise CloudflareError(f"{method} {path} failed: {pretty(parsed)}")
        return parsed.get("result")

    def get_zone(self, domain: str) -> Dict[str, Any]:
        zones = self.request("GET", "/zones", params={"name": domain})
        if not zones:
            raise CloudflareError(f"No Cloudflare zone found for {domain}")
        return zones[0]

    def get_pages_project(self, account_id: str, project_name: str) -> Dict[str, Any]:
        return self.request("GET", f"/accounts/{account_id}/pages/projects/{project_name}")

    def list_pages_domains(self, account_id: str, project_name: str) -> List[Dict[str, Any]]:
        return self.request("GET", f"/accounts/{account_id}/pages/projects/{project_name}/domains") or []

    def create_pages_domain(self, account_id: str, project_name: str, domain_name: str) -> Dict[str, Any]:
        return self.request(
            "POST",
            f"/accounts/{account_id}/pages/projects/{project_name}/domains",
            payload={"name": domain_name},
        )

    def retry_pages_domain(self, account_id: str, project_name: str, domain_name: str) -> Dict[str, Any]:
        return self.request(
            "PATCH",
            f"/accounts/{account_id}/pages/projects/{project_name}/domains/{domain_name}",
            payload={},
        )

    def list_dns_records(self, zone_id: str, fqdn: str) -> List[Dict[str, Any]]:
        return self.request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"name.exact": fqdn, "match": "all", "per_page": 100},
        ) or []

    def delete_dns_record(self, zone_id: str, record_id: str) -> None:
        self.request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")

    def patch_zone_ssl(self, zone_id: str, mode: str) -> Dict[str, Any]:
        return self.request("PATCH", f"/zones/{zone_id}/settings/ssl", payload={"value": mode})


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def inspect_local_cloudflare_setup() -> None:
    wrangler_file = Path("wrangler.jsonc")
    if not wrangler_file.exists():
        return

    print_section("Local Cloudflare config")
    print("Found wrangler.jsonc in this repo.")
    print("That means Cloudflare Git auto-configured this project as a Worker/static-assets deploy.")
    print("This lines up with the live *.workers.dev URL.")
    text = wrangler_file.read_text(encoding="utf-8", errors="replace")
    if '"pattern": "pictureperfectprojects321.com/*"' in text:
        print("Custom domain routes are present in wrangler.jsonc.")
    else:
        print("Custom domain routes are missing from wrangler.jsonc.")


def summarize_dns_response(name: str, record_type: str, payload: Dict[str, Any]) -> None:
    status = payload.get("Status")
    answers = payload.get("Answer", [])
    print(f"{name} {record_type}: status={status}")
    for answer in answers:
        print(f"  - {answer.get('type')} {answer.get('data')}")


def audit_public(domain: str, worker_url: Optional[str]) -> Dict[str, Any]:
    root = domain
    www = f"www.{domain}"

    print_section("Public DNS audit")
    root_a = public_dns_lookup(root, "A")
    root_aaaa = public_dns_lookup(root, "AAAA")
    www_cname = public_dns_lookup(www, "CNAME")
    root_ns = public_dns_lookup(root, "NS")

    summarize_dns_response(root, "A", root_a)
    summarize_dns_response(root, "AAAA", root_aaaa)
    summarize_dns_response(www, "CNAME", www_cname)
    summarize_dns_response(root, "NS", root_ns)

    print_section("HTTPS audit")
    domain_urls = [f"https://{domain}", f"https://www.{domain}"]
    if worker_url:
        domain_urls.append(worker_url)

    http_results = []
    for url in domain_urls:
        result = http_head(url)
        http_results.append(result)
        status = result.get("status", "ERR")
        final_url = result.get("final_url", "")
        print(f"{url} -> {status} {final_url}")
        error = result.get("error")
        if error:
            print(f"  error: {error}")
        headers = result.get("headers", {})
        location = headers.get("Location") or headers.get("location")
        if location:
            print(f"  location: {location}")

    return {
        "root_a": root_a,
        "root_aaaa": root_aaaa,
        "www_cname": www_cname,
        "root_ns": root_ns,
        "http_results": http_results,
    }


def needs_parking_cleanup(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bad = []
    for record in records:
        content = str(record.get("content", "")).lower()
        if "parkingpage.namecheap.com" in content:
            bad.append(record)
    return bad


def ensure_pages_domains(
    client: CloudflareClient,
    *,
    account_id: str,
    project_name: str,
    zone_id: str,
    domain: str,
    include_www: bool,
    ssl_mode: Optional[str],
) -> None:
    target_domains = [domain]
    if include_www:
        target_domains.append(f"www.{domain}")

    print_section("Cloudflare project check")
    project = client.get_pages_project(account_id, project_name)
    print(f"Pages project: {project.get('name')}")
    print(f"Pages subdomain: {project.get('subdomain')}")

    print_section("DNS cleanup")
    for fqdn in target_domains:
        records = client.list_dns_records(zone_id, fqdn)
        parking = needs_parking_cleanup(records)
        if not parking:
            print(f"{fqdn}: no Namecheap parking record found")
            continue
        for record in parking:
            print(f"Deleting bad record on {fqdn}: {record.get('type')} -> {record.get('content')}")
            client.delete_dns_record(zone_id, record["id"])

    print_section("Pages domains")
    existing = {item["name"]: item for item in client.list_pages_domains(account_id, project_name)}
    for fqdn in target_domains:
        if fqdn not in existing:
            print(f"Adding Pages custom domain: {fqdn}")
            existing[fqdn] = client.create_pages_domain(account_id, project_name, fqdn)
        else:
            print(f"Pages custom domain already exists: {fqdn}")

        if existing[fqdn].get("status") != "active":
            print(f"Retrying validation for {fqdn} (current status: {existing[fqdn].get('status')})")
            existing[fqdn] = client.retry_pages_domain(account_id, project_name, fqdn)

    if ssl_mode:
        print_section("SSL mode")
        ssl_result = client.patch_zone_ssl(zone_id, ssl_mode)
        print(f"Zone SSL mode set to: {ssl_result.get('value')}")

    print_section("Domain status summary")
    final_domains = {item["name"]: item for item in client.list_pages_domains(account_id, project_name)}
    for fqdn in target_domains:
        item = final_domains.get(fqdn)
        if not item:
            print(f"{fqdn}: missing from Pages after update")
            continue
        print(f"{fqdn}: status={item.get('status')}, verification={item.get('verification_data', {}).get('status')}")
        validation = item.get("validation_data", {})
        error_message = validation.get("error_message") or item.get("verification_data", {}).get("error_message")
        if error_message:
            print(f"  error: {error_message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and repair Cloudflare domain wiring.")
    parser.add_argument("mode", choices=["audit", "fix"], help="Run a public audit or apply Cloudflare fixes.")
    parser.add_argument("--domain", default="pictureperfectprojects321.com", help="Apex domain to inspect.")
    parser.add_argument(
        "--worker-url",
        default="https://pictureperfectprojects321.digitalreflectionmedia.workers.dev/",
        help="Optional live Cloudflare URL to compare against.",
    )
    parser.add_argument("--project", default=env("CF_PAGES_PROJECT_NAME", "pictureperfectprojects321"))
    parser.add_argument("--account-id", default=env("CF_ACCOUNT_ID"))
    parser.add_argument("--zone-id", default=env("CF_ZONE_ID"))
    parser.add_argument("--api-token", default=env("CF_API_TOKEN"))
    parser.add_argument("--skip-www", action="store_true", help="Only manage the apex domain.")
    parser.add_argument(
        "--ssl-mode",
        default=None,
        choices=["off", "flexible", "full", "strict"],
        help="Optional Cloudflare SSL mode to apply during fix mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        inspect_local_cloudflare_setup()
        audit_public(args.domain, args.worker_url)

        if args.mode == "audit":
            return 0

        if not args.api_token:
            print("\nCF_API_TOKEN is required for fix mode.", file=sys.stderr)
            return 2
        if not args.account_id:
            print("\nCF_ACCOUNT_ID is required for fix mode.", file=sys.stderr)
            return 2

        client = CloudflareClient(args.api_token)
        zone_id = args.zone_id
        if not zone_id:
            zone = client.get_zone(args.domain)
            zone_id = zone["id"]
            print(f"\nResolved zone id: {zone_id}")

        ensure_pages_domains(
            client,
            account_id=args.account_id,
            project_name=args.project,
            zone_id=zone_id,
            domain=args.domain,
            include_www=not args.skip_www,
            ssl_mode=args.ssl_mode,
        )

        print_section("Re-checking public DNS and HTTPS")
        time.sleep(2)
        audit_public(args.domain, args.worker_url)
        return 0
    except CloudflareError as exc:
        print(f"\nCloudflare API error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
