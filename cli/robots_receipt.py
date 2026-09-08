"""Hashable robots policy provenance helpers."""
import hashlib, time
def fingerprint(lines): return hashlib.sha256("\n".join(lines).encode()).hexdigest()
def decision(policy, status, lines=(), authorization_ref=None):
    return {'mode':policy,'fetch_status':status,'policy_fingerprint':fingerprint(lines) if lines else None,'fetched_at':time.time(),'authorization_ref':authorization_ref if policy=='ignore_authorised' else None}
