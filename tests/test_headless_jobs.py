import tempfile, unittest
from cli.jobs import JobStore
from unittest.mock import patch
import mcp.server as mcp_server
class Jobs(unittest.TestCase):
 def test_idempotent_lifecycle_and_lease(self):
  with tempfile.NamedTemporaryFile() as f:
   s=JobStore(f.name); a=s.start({'profile_id':'fixture'}); self.assertEqual(s.start({'profile_id':'fixture'})['run_id'],a['run_id']); self.assertTrue(s.acquire(a['run_id'])); self.assertFalse(s.acquire(a['run_id'])); s.transition(a['run_id'],'paused'); self.assertTrue(s.acquire(a['run_id'])); s.transition(a['run_id'],'complete'); self.assertFalse(s.acquire(a['run_id'])); s.close()
 def test_opt_in_schedule_and_redacted_notification(self):
  with tempfile.NamedTemporaryFile() as f:
   s=JobStore(f.name); st=s.start({'profile_id':'fixture'}); n=s.notification(st); self.assertNotIn('profile_id',n); self.assertRaises(ValueError,JobStore.schedule,{'enabled':False}); self.assertEqual(JobStore.schedule({'enabled':True,'interval_seconds':60})['overlap_policy'],'skip'); s.close()
 def test_mcp_lifecycle_is_scoped(self):
  with tempfile.TemporaryDirectory() as d, patch.object(mcp_server, 'REPO_ROOT', d):
   st=mcp_server.handle_tool_call('job_start', {'spec':{'profile_id':'fixture'}})
   self.assertEqual(mcp_server.handle_tool_call('job_status', {'run_id':st['run_id']})['state'],'queued')
   self.assertEqual(mcp_server.handle_tool_call('job_transition', {'run_id':st['run_id'],'state':'cancelled'})['state'],'cancelled')
if __name__=='__main__': unittest.main()
