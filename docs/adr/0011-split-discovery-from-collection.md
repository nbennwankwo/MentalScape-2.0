# ADR 0011 Discover files from a browser, collect them on GitHub Actions

- **Status** Accepted
- **Date** 2026-10-22
- **Decided by** Kemi Ben-Nwankwo

## Context

The first trial run of the ingest workflow failed. A diagnostic run on GitHub Actions showed that NHS England serves two hosts that behave differently for cloud servers.

| Host | What it serves | Response to a GitHub runner |
|---|---|---|
| `digital.nhs.uk` | release pages, robots.txt, sitemap | 403 with a Cloudflare "Just a moment" bot challenge, whatever the user agent |
| `files.digital.nhs.uk` | the data files | 200, files download normally |

NHS England's robots.txt allows all crawlers, so the challenge looks like general bot protection against cloud traffic rather than a ban on reuse. Getting around a bot challenge would be wrong in principle and would undermine the project's credibility, so it is not an option.

## Decision

1. **Discovery** reads the release pages from a normal browser using `tools/discover_in_browser.js`, which saves a list of download cards. The `classify` command turns that list into `data/reference/mhsds_catalogue.csv`, which is committed through a pull request like any other change.
2. **Collection** runs on GitHub Actions. The `collect` command downloads every wanted file in the committed catalogue that is not yet in the manifest, straight from `files.digital.nhs.uk`, and the workflow publishes it to the data release.
3. **Staleness check.** The weekly scheduled run fails if the newest main data file in the catalogue is more than three months old, so a forgotten refresh shows up as a failed run and an email.
4. The direct `discover` command stays in the code for any network NHS England does allow, and explains the block clearly when it meets one.
5. NHS England will be asked whether there is a supported API or a way to allowlist this project, which would make discovery fully automatic.

## Alternatives considered

- **Run a self hosted runner on a personal laptop.** Only works while the laptop is on, and may meet the same challenge.
- **Read pages through a third party summariser.** Not exact enough for file addresses.
- **Wait for NHS England.** Would stall Phase 1 for an unknown time.

## Consequences

Collection, checksums, storage and every later step are fully automatic. Discovery needs a short browser step about once a month, after each NHS England release, which takes a few minutes. The catalogue is now versioned in git, so every change in what NHS England publishes shows up as a reviewable diff.
