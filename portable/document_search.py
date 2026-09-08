"""Offline full-text search over catalogue derivatives."""
import sqlite3
class SearchIndex:
    def __init__(self, catalogue): self.db=catalogue.db; self.db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS text_index USING fts5(derivative_id UNINDEXED,text,source_id UNINDEXED,revision_id UNINDEXED)'); self.db.commit()
    def add(self, result, source_id, revision_id, handling='unknown', kind='text'):
        did=result.get('derivative_id') or result['output_hash']; self.db.execute('INSERT OR REPLACE INTO derivatives VALUES (?,?,?,?,?,?,?,?,?)',(did,revision_id,kind,result.get('extractor','builtin'),result.get('output_hash',''),result['status'],result.get('text',''),str(result.get('locators',[])),handling)); self.db.execute('INSERT OR REPLACE INTO text_index VALUES (?,?,?,?)',(did,result.get('text',''),source_id,revision_id)); self.db.commit(); return did
    def search(self, query, source_id=None, limit=20):
        sql='SELECT derivative_id,text,source_id,revision_id FROM text_index WHERE text_index MATCH ?'; args=[query]
        if source_id: sql+=' AND source_id=?'; args.append(source_id)
        sql+=' LIMIT ?'; args.append(limit); return [dict(zip(('derivative_id','text','source_id','revision_id'),r)) for r in self.db.execute(sql,args)]
