const {test,expect}=require('playwright/test');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {spawnSync}=require('node:child_process');
const crypto=require('node:crypto');
const python=process.env.AEGIS_TEST_PYTHON || (process.platform==='win32'?'python':'python3');
const root=path.resolve(__dirname,'../..');
test('an unexecuted receipt cannot qualify a mirroring platform',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'aegis receipt contract '));
  try {
    const output=path.join(dir,'pending.json');
    const result=spawnSync(python,['scripts/mirroring_acceptance.py','--output',output],{cwd:root,encoding:'utf8'});
    expect(result.status,result.stderr).toBe(0);
    const receipt=JSON.parse(await fs.readFile(output,'utf8'));
    expect(receipt.schema).toBe('aegis.mirroring-acceptance.v2');
    expect(receipt.qualification_status).toBe('pending');
    const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/mirroring-site.json'),'utf8'));
    expect(receipt.fixture_hashes).toEqual(Object.fromEntries(Object.entries(fixture).map(([name,value])=>[name,crypto.createHash('sha256').update(value.body).digest('hex')])));
    expect(receipt.offline).toBeNull();
    const checked=spawnSync(python,['scripts/mirroring_acceptance.py','--check','--output',output],{cwd:root,encoding:'utf8'});
    expect(checked.status).not.toBe(0);
    receipt.qualification_status='passed';
    await fs.writeFile(output,JSON.stringify(receipt));
    const forged=spawnSync(python,['scripts/mirroring_acceptance.py','--check','--output',output],{cwd:root,encoding:'utf8'});
    expect(forged.status).not.toBe(0);
  } finally {await fs.rm(dir,{recursive:true,force:true});}
});
test('fixture payload identities are deterministic and include real CSS and image bytes',async()=>{
  const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/mirroring-site.json'),'utf8'));
  expect(Object.keys(fixture)).toContain('/site.css');expect(Object.keys(fixture)).toContain('/asset.svg');
  const hashes=Object.fromEntries(Object.entries(fixture).map(([name,value])=>[name,crypto.createHash('sha256').update(value.body).digest('hex')]));
  expect(hashes['/site.css']).toMatch(/^[a-f0-9]{64}$/);
  expect(fixture['/asset.svg'].body).toContain('width="12"');
  expect(fixture['/second.html'].body).toContain('/third.html');
});
