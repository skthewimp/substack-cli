# Security

This fork adds credential, network, asset and content safeguards described in
[HARDENING.md](HARDENING.md). Its security tests run offline.

Report suspected vulnerabilities privately to the fork owner through GitHub when
private reporting is available. For vulnerabilities inherited from upstream, use the
upstream repository's private reporting channel. Do not post session cookies or private
article content in issues, logs or pull requests.

The implementation deliberately blocks redirects and HTTP publication URLs. Explicit
configuration is trusted input. Runtime isolation and a pinned reviewed version remain
necessary; session cookies grant account access and private APIs can change.
