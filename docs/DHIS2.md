# Connecting to DHIS2

DHIS2 is the national health information system. PHEM weekly disease reports and EPI vaccination data live there. The connector is `connectors/dhis2.py`.

## Ground rules
- **No Ethiopian data is pulled until EPHI approves in writing.** The code enforces this. Data values can only be pulled from the public DHIS2 demo, unless `DHIS2_PULL_APPROVED=true` is set in `.env`. Reading the list of organisation units (metadata) is always allowed.
- **Credentials live only in `.env`, never in code or git.** Prefer a personal access token (`DHIS2_TOKEN`) with read-only rights over a username and password.

## Try it on the public demo
1. In `.env`:
   ```
   DHIS2_URL=https://play.im.dhis2.org/stable-2-41-4
   DHIS2_USERNAME=admin
   DHIS2_PASSWORD=district
   ```
   These are the demo's published credentials. Check https://play.dhis2.org for the current server address, because the demo versions change.
2. Run `python scripts/dhis2_check.py`. It prints the server version and how many organisation units it has at each level.

The demo uses a made-up country (Sierra Leone-like data), so `--link` will find no Ethiopian matches there. That's expected.

## With EPHI's DHIS2 (after approval)
1. Set `DHIS2_URL` and `DHIS2_TOKEN` for the Ethiopian server, and load the OCHA boundaries first (DATABASE_SETUP step 6).
2. `python scripts/dhis2_check.py --link` proposes a link from each DHIS2 unit to a P-code. Ambiguous and unmatched units are listed for a person to resolve; nothing is saved yet.
3. `python scripts/dhis2_check.py --link --apply` saves the confident links (`org_units.dhis2_uid`).
4. Only then, and only with `DHIS2_PULL_APPROVED=true`, weekly measles counts can be pulled and stored. Which DHIS2 data elements mean "suspected" and "lab-confirmed" measles is instance-specific configuration; we'll set it with EPHI's DHIS2 administrator.
