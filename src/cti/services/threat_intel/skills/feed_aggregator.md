# Feed Aggregator

Pull open-source security intel from configured feeds, dedup against prior runs,
triage new items against the operator's environments, and advance critical
findings into sourced deep-dive reports via the research → writer model chain.

## Pipeline

1. **Fetch** — run the feed aggregator engine with the instance config; read the JSON report.
2. **Triage** — classify every new item against homelab / real-world chatter.
3. **Deep-dive** — for items that earn a chain, call the research model then the writer model.
4. **Persist** — save the writer output as an Emergent CTI Report with AI provenance.

## Environments (homelab-first)

- **Homelab / home-network:** Proxmox, Docker, UniFi, Linux, self-hosted services, home network gear. Homelab detections are Elastic-only.
- **Real-world chatter:** active exploitation, CISA KEV additions, named campaigns, heavy current attention.

## Deep-dive bar

An item earns a research+writer chain when it matches a environment bucket **or**
carries exploitation/KEV/heavy-chatter signal against something the estate
actually touches. CVSS-critical junk (SOHO routers, niche WordPress plugins,
regional ERP) without estate exposure stays list-only.

## Bulletin bar (publication gate)

Two legs, both required:

1. **Exploitation** — confirmed in-wild exploitation of a *named CVE* via CISA KEV
   or explicit primary-IR-vendor attribution. PoC-only / unconfirmed / mass scanning
   do not count. No CVE → cannot clear.
2. **Reachability** — remotely reachable pre-auth (or near-pre-auth with trivially
   obtainable auth) on software an SMB / mid-market defender actually runs.
   Local-only or meaningful-privilege-required fails this leg.

CVSS is reporting, not gating. Cite every score with scorer and version; never
convert between CVSS versions.

## Budget

On a scheduled fire, budget **two** full research+writer chains. Defer a third
with honest framing. Partial digests that name their gaps are successes.

## Hard rules

- Prefer primary sources (vendor advisories, CSAF/CVRF, NVD, CISA KEV).
- Do not invent CVE details, IOCs, or detections.
- Check each CVE against KEV individually (`kev_check`).
- Defender altitude only — no exploit recipes.
