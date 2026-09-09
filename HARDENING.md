# Hardened publishing fork

This fork starts from upstream commit 38a13c173e7dbedec82cf9d9786529b7e09056d9.
Use an exact reviewed commit, not an automatically updated branch.

## Changed behavior

- Credentials come from one explicit `--config` file, the user config, or a complete
  environment identity. Checkout/parent `.substack.json` files are never discovered.
  Set both `SUBSTACK_PUBLICATION_URL` and `SUBSTACK_SESSION_TOKEN` together.
- Publication URLs must be HTTPS origins. All HTTP redirects are refused, ambient
  proxy settings are ignored, and remote error bodies are not echoed.
- Credential files are replaced atomically with owner-only permissions.
- Only reads retry automatically. After a failed write, inspect remote state before
  retrying; the operation may already have succeeded.
- Local article images and covers must stay within the article directory. Uploads
  must also stay inside `SUBSTACK_ASSET_ROOT` (default: current working directory).
  Symlinks are resolved. PNG/JPEG/GIF/WebP signatures and a 20 MiB size limit are
  checked. This is a format gate, not malware scanning or full image decoding.
- Pull downloads accept only HTTPS Substack CDN hosts, without redirects, and enforce
  a 20 MiB limit. Remote slugs cannot escape the output directory.
- Conversion warnings stop push/update/render rather than publishing partial content.
  Offline render validates local images without uploading them. Tables require Pillow;
  their output directory must also be inside the approved asset root for uploads.
- Publishing and scheduling are web-only unless `--send-email` is explicit.
- `update --yes` runs its own audit. Changed/removed text, different image URLs,
  structure loss, or dropped native blocks require a reviewed `--accept-live-sha256`.
  `audit --json` provides that fingerprint and the removed text/image references.
  The fingerprint is a concurrency guard, not proof a human reviewed anything.
- Live records are backed up before update to `SUBSTACK_BACKUP_DIR` or
  `~/.local/state/substack-cli/backups`. A failed backup blocks the write. The remote
  revision is rechecked immediately before writing. Backups contain private content.

## Review an intentional replacement

```bash
substack audit posts/article.md --json
# Compare the local article, live content, removed_text and removed_images.
substack update posts/article.md --yes --accept-live-sha256 <reviewed-live-sha256>
```

Do not mechanically feed the audit hash into update. Preserve a readable preview,
review changes, and retain the backup. Updating Substack is not transactional: its
private API does not provide a documented conditional write here, so a concurrent
editor change in the final read/write window remains possible. Avoid concurrent edits.

A clean audit is conservative evidence, not a guarantee of identical formatting.
Newly uploaded copies of the same image have different URLs and require review.
Backups are JSON snapshots for recovery; there is no automatic restore command.

## Execution boundary

A Python virtual environment is not a security sandbox. Run this CLI in a container
or filesystem sandbox exposing only the selected post, assets, credential and backup
directory. Restrict authenticated destinations to the intended publication; do not
pass untrusted environment/configuration to the process. Do not give an agent the
ability to replace its own approved runtime or change the publication configuration.
Session cookies remain account credentials, not narrowly scoped publishing tokens.

## Maintenance

Review upstream changes before incorporating them. Keep the runtime pinned. The
upstream project uses private Substack APIs; authentication and compatibility require
ongoing maintenance. Run `pytest -q` and `ruff check .` before publishing changes to
this fork. Security checks are offline and do not prove current Substack compatibility.
