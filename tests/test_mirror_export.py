import tempfile, unittest, zipfile
from pathlib import Path
from cli.export_mirror import safe_path, export_directory, export_zip
class ExportTests(unittest.TestCase):
 def test_paths_and_query_identity(self):
  self.assertEqual(safe_path('https://fixture.test/'), 'index.html')
  self.assertIn('__q_', safe_path('https://fixture.test/a?x=1'))
  with self.assertRaises(ValueError): safe_path('file:///etc/passwd')
 def test_directory_manifest_and_deterministic_zip(self):
  records=[('https://fixture.test/b',b'b'),('https://fixture.test/',b'a')]
  with tempfile.TemporaryDirectory() as t:
   m=export_directory(records,Path(t)/'d'); self.assertEqual(len(m),2); self.assertTrue((Path(t)/'d/manifest.json').exists())
   export_zip(records,Path(t)/'a.zip'); export_zip(records,Path(t)/'b.zip'); self.assertEqual((Path(t)/'a.zip').read_bytes(),(Path(t)/'b.zip').read_bytes())
   with zipfile.ZipFile(Path(t)/'a.zip') as z: self.assertIn('manifest.json',z.namelist())
