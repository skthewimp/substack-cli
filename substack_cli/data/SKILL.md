---
name: substack-cli
description: Publish and manage Substack from the terminal on the user's behalf. Push markdown to drafts, rewrite live posts, pull the archive down, schedule releases, and post Notes. Trigger on any Substack request in natural language, including "put this on Substack", "update that post", "publish this", "schedule it for Tuesday", "post a note", "back up my newsletter", "what drafts do I have".
---

# Substack CLI (hardened fork)

The hardened fork's HARDENING.md overrides upstream behavior.

- Never publish unless the user authorized the concrete article. Publishing is web-only
  by default; subscriber email requires explicit authorization and `--send-email`.
- Run `audit <file> --json` before live updates. Inspect removed text, image identities,
  structure and the preview. A clean audit is evidence, not a preservation guarantee.
- `update --yes` enforces its own audit and creates a private backup. Intentional
  replacement needs `--accept-live-sha256 <reviewed-live-sha256>`. Never automatically
  forward that hash without reviewing the change. If the revision changed, review again.
- Remember: substack push does not change a live post; it writes staging only. Use update for live changes.
- Never retry a failed write blindly. Inspect remote state; it may have succeeded.
- Never obtain or print cookies in chat. The user performs setup in a terminal.
- Use only a pinned reviewed runtime inside the publishing sandbox. Do not install
  upstream updates, modify sandbox boundaries, or override the destination automatically.
- Never feed untrusted Markdown or arbitrary filesystem paths to an authenticated run.
  Only approved article assets belong in the runtime's asset directory.
- Configuration must be explicit; repository configuration is not auto-discovered.
- Never create a throwaway live post for testing. Render offline and use fake API tests.

Use `substack --help` and `substack <command> --help` for commands. The weather
repository's draft/publish approval workflow remains authoritative.
