import tempfile,unittest
from cli.durable_job import DurableCaptureJob
class DurableTests(unittest.TestCase):
 def test_resume_reloads_checkpoint_and_lease(self):
  with tempfile.TemporaryDirectory() as t:
   j=DurableCaptureJob(t,'p','h'); s=j.start({'profile_id':'p'}); j.checkpoint.save([],['a'],[]); r=j.resume(s['run_id']); self.assertEqual(r['job']['state'],'running'); j.close()
 def test_cancel_is_explicit(self):
  with tempfile.TemporaryDirectory() as t:
   j=DurableCaptureJob(t,'p','h'); s=j.start({'profile_id':'p'}); self.assertEqual(j.cancel(s['run_id'])['state'],'cancelled'); j.close()
