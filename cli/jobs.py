"""Dependency-free, opt-in job lifecycle store for headless capture orchestration."""
from __future__ import annotations
import hashlib, json, os, sqlite3, time
from pathlib import Path

STATES = {'queued','running','paused','complete','partial','auth-required','failed','cancelled'}
TERMINAL = {'complete','partial','auth-required','failed','cancelled'}

class JobStore:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = str(path); Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path); self.db.execute('PRAGMA busy_timeout=3000')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL, event TEXT, updated REAL NOT NULL, lease REAL)'); self.db.commit()
    def close(self): self.db.close()
    def start(self, spec: dict, run_id: str | None = None) -> dict:
        if not isinstance(spec, dict) or not isinstance(spec.get('profile_id'), str): raise ValueError('profile_id required')
        rid = run_id or hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:32]
        now=time.time(); encoded=json.dumps(spec, sort_keys=True)
        self.db.execute('INSERT OR IGNORE INTO jobs VALUES (?,?,?,?,?,NULL)', (rid,encoded,'queued','start',now)); self.db.commit()
        return self.status(rid)
    def status(self, run_id: str) -> dict:
        row=self.db.execute('SELECT id,spec,state,event,updated,lease FROM jobs WHERE id=?',(run_id,)).fetchone()
        if not row: raise KeyError(run_id)
        return {'run_id':row[0],'spec':json.loads(row[1]),'state':row[2],'event':row[3],'updated':row[4],'lease':row[5]}
    def transition(self, run_id: str, state: str, event: str = '') -> dict:
        if state not in STATES: raise ValueError('invalid state')
        current=self.status(run_id)
        allowed={'queued':{'running','cancelled'},'running':{'paused','complete','partial','auth-required','failed','cancelled'},'paused':{'running','cancelled'}}
        if current['state'] in TERMINAL or state not in allowed.get(current['state'],set()): raise ValueError('invalid transition')
        self.db.execute('UPDATE jobs SET state=?,event=?,updated=? WHERE id=?',(state,event,time.time(),run_id)); self.db.commit(); return self.status(run_id)
    def acquire(self, run_id: str, lease_seconds: int = 300) -> bool:
        if lease_seconds < 1: raise ValueError('invalid lease')
        now=time.time(); row=self.db.execute('SELECT state,lease FROM jobs WHERE id=?',(run_id,)).fetchone()
        if not row: raise KeyError(run_id)
        if row[0] not in ('queued','paused','running') or (row[0]=='running' and row[1] and row[1] > now): return False
        self.db.execute('UPDATE jobs SET state="running",lease=?,updated=?,event="lease-acquired" WHERE id=?',(now+lease_seconds,now,run_id)); self.db.commit(); return True
    def release(self, run_id: str):
        self.db.execute('UPDATE jobs SET lease=NULL,updated=? WHERE id=?',(time.time(),run_id)); self.db.commit()
    @staticmethod
    def notification(status: dict) -> dict:
        return {'run_id':status['run_id'],'state':status['state'],'event':status['event'],'updated':status['updated'],'summary_hash':hashlib.sha256(json.dumps(status.get('spec',{}),sort_keys=True).encode()).hexdigest()}
    @staticmethod
    def schedule(spec: dict) -> dict:
        if not isinstance(spec,dict) or not spec.get('enabled') is True: raise ValueError('schedule is opt-in; enabled must be true')
        if not isinstance(spec.get('interval_seconds'),int) or spec['interval_seconds'] < 60: raise ValueError('interval_seconds must be >= 60')
        return {'version':1,'enabled':True,'interval_seconds':spec['interval_seconds'],'misfire_policy':spec.get('misfire_policy','skip'),'overlap_policy':spec.get('overlap_policy','skip')}
