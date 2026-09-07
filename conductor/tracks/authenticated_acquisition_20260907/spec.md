# Specification

Authentication is opt-in. Supported strategies are imported headers/cookies, basic authentication, client certificates, and explicit browser hand-off. Secrets are referenced externally, redacted from logs and WARC request records, scope-limited, and expiry-aware.
