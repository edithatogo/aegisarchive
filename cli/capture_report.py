"""Reconcile capture progress, integrity, coverage and replay readiness."""
def summarize(outcomes, integrity='unknown', replay='unknown'):
    values=list(outcomes or []); counts={}
    for item in values: counts[item.get('state','unknown')]=counts.get(item.get('state','unknown'),0)+1
    attempted=sum(v for k,v in counts.items() if k not in ('excluded','pending')); saved=counts.get('saved',0)
    status='complete' if attempted and saved==attempted else 'partial' if saved else 'unknown'
    return {'schema_version':1,'attempted':attempted,'saved':saved,'excluded':counts.get('excluded',0),'failed':counts.get('failed',0),'pending':counts.get('pending',0),'coverage':{'in_scope_attempted':attempted,'saved':saved,'status':status},'integrity':integrity if integrity in ('verified','failed','unknown') else 'unknown','replay_readiness':replay if replay in ('ready','partial','blocked','unknown') else 'unknown'}
