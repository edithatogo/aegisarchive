"""Classify failures and select bounded, operator-requested retries."""
RETRYABLE = {0, 408, 425, 429, 500, 502, 503, 504}
def classify(status, error_type=None):
    if status in RETRYABLE: return 'transient'
    if status in (401,403): return 'access_denied'
    if status == 404: return 'not_found'
    if status and 400 <= status < 500: return 'permanent_client'
    return 'network' if error_type else 'unknown'
def select(outcomes, urls, limit=3):
    chosen=[]
    for url in urls:
        item=outcomes.get(url, {}); status=item.get('status');
        if classify(status, item.get('error_type')) in ('transient','network'):
            chosen.append(url)
        if len(chosen)>=max(0,limit): break
    return chosen
