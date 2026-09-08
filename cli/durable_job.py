"""Small durable job facade joining lifecycle state to a verified checkpoint."""
from .jobs import JobStore
from .mirror_checkpoint import MirrorCheckpoint

class DurableCaptureJob:
    def __init__(self, root, profile_id, profile_hash):
        self.store=JobStore(str(root)+'/jobs.sqlite'); self.checkpoint=MirrorCheckpoint(str(root)+'/mirror',profile_id,profile_hash)
    def start(self, spec): return self.store.start(spec)
    def resume(self, run_id):
        status=self.store.status(run_id); state=self.checkpoint.load()
        if status['state'] in ('queued','paused'): self.store.acquire(run_id)
        return {'job':self.store.status(run_id),'checkpoint':state}
    def cancel(self, run_id): return self.store.transition(run_id,'cancelled','operator-cancelled')
    def close(self): self.store.close()
