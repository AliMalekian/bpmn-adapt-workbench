"""DB-API repository implementation shared by SQLite and PostgreSQL."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .repositories import ApprovalRequired
from .migrator import MigrationRunner


SCHEMA = (
    "CREATE TABLE IF NOT EXISTS processes (process_id TEXT PRIMARY KEY, folder TEXT NOT NULL, name TEXT NOT NULL, narrative TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS process_versions (version_id TEXT PRIMARY KEY, process_id TEXT NOT NULL, parent_version_id TEXT, bpmn_xml TEXT NOT NULL, checksum TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(process_id) REFERENCES processes(process_id))",
    "CREATE TABLE IF NOT EXISTS rules (process_id TEXT NOT NULL, rule_id TEXT NOT NULL, text TEXT NOT NULL, PRIMARY KEY(process_id, rule_id))",
    "CREATE TABLE IF NOT EXISTS resources (process_id TEXT NOT NULL, resource_id TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(process_id, resource_id))",
    "CREATE TABLE IF NOT EXISTS runtime_states (process_id TEXT NOT NULL, state_id TEXT NOT NULL, position TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(process_id, state_id))",
    "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, process_id TEXT NOT NULL, config_fingerprint TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, process_id TEXT NOT NULL, source_version_id TEXT, operation TEXT NOT NULL, raw_text TEXT NOT NULL, target_element TEXT NOT NULL, payload_json TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS decisions (decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, payload_json TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS candidates (candidate_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, source_version_id TEXT NOT NULL, bpmn_xml TEXT NOT NULL, checksum TEXT NOT NULL, payload_json TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS simulations (report_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candidate_id TEXT NOT NULL, passed INTEGER NOT NULL, payload_json TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS provenance_events (run_id TEXT NOT NULL, sequence_no INTEGER NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(run_id, sequence_no))",
    "CREATE TABLE IF NOT EXISTS rag_cases (evidence_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, process_id TEXT NOT NULL, source_version_id TEXT, operation TEXT NOT NULL, text TEXT NOT NULL, decision TEXT NOT NULL, metadata_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, revoked_reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS retrieval_logs (retrieval_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, query_hash TEXT NOT NULL, filters_json TEXT NOT NULL, scores_json TEXT NOT NULL, ranking_json TEXT NOT NULL, index_version TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
)


@dataclass(frozen=True)
class RepositoryHealth:
    status: str
    schema_version: str | None
    detail: str


class RelationalDatabase:
    placeholder = "?"
    dialect = "sqlite"

    def __init__(self, connection):
        self.connection = connection

    def _sql(self, sql: str) -> str:
        return sql if self.placeholder == "?" else sql.replace("?", self.placeholder)

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        cursor = self.connection.cursor()
        cursor.execute(self._sql(sql), params)
        return cursor

    def initialize(self):
        return MigrationRunner().upgrade(self.connection, self.dialect)

    def health(self) -> RepositoryHealth:
        try:
            cur = self.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            version = None if row is None else (row["version"] if hasattr(row, "keys") else row[0])
            return RepositoryHealth("READY", version, "database connection and schema are available")
        except Exception as exc:
            return RepositoryHealth("NOT_READY", None, f"schema health check failed: {type(exc).__name__}")

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _dict(row, cursor=None) -> dict[str, Any] | None:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return dict(row)
        return dict(zip([d[0] for d in cursor.description], row))

    def upsert_process(self, process_id, folder, name, narrative, bpmn_xml, rules, resources, states) -> None:
        self.execute("INSERT INTO processes(process_id,folder,name,narrative) VALUES(?,?,?,?) ON CONFLICT(process_id) DO UPDATE SET folder=excluded.folder,name=excluded.name,narrative=excluded.narrative", (process_id, folder, name, narrative))
        import hashlib
        version_id = f"{process_id}-source"
        checksum = hashlib.sha256(bpmn_xml.encode()).hexdigest()
        self.execute("INSERT INTO process_versions(version_id,process_id,parent_version_id,bpmn_xml,checksum) VALUES(?,?,?,?,?) ON CONFLICT(version_id) DO UPDATE SET bpmn_xml=excluded.bpmn_xml,checksum=excluded.checksum", (version_id, process_id, None, bpmn_xml, checksum))
        for rule_id, text in rules:
            self.execute("INSERT INTO rules(process_id,rule_id,text) VALUES(?,?,?) ON CONFLICT(process_id,rule_id) DO UPDATE SET text=excluded.text", (process_id, rule_id, text))
        for resource_id, resource_name, value in resources:
            self.execute("INSERT INTO resources(process_id,resource_id,name,value) VALUES(?,?,?,?) ON CONFLICT(process_id,resource_id) DO UPDATE SET name=excluded.name,value=excluded.value", (process_id, resource_id, resource_name, value))
        for state_id, position, payload in states:
            self.execute("INSERT INTO runtime_states(process_id,state_id,position,payload_json) VALUES(?,?,?,?) ON CONFLICT(process_id,state_id) DO UPDATE SET position=excluded.position,payload_json=excluded.payload_json", (process_id, state_id, position, payload))
        self.connection.commit()

    def get_process(self, process_id):
        cur = self.execute("SELECT * FROM processes WHERE process_id=?", (process_id,)); return self._dict(cur.fetchone(), cur)

    def get_version(self, version_id):
        cur = self.execute("SELECT * FROM process_versions WHERE version_id=?", (version_id,)); return self._dict(cur.fetchone(), cur)

    def save_process_version(self, version_id, process_id, parent_version_id, bpmn_xml, checksum):
        self.execute("INSERT INTO process_versions(version_id,process_id,parent_version_id,bpmn_xml,checksum) VALUES(?,?,?,?,?)", (version_id,process_id,parent_version_id,bpmn_xml,checksum)); self.connection.commit()

    def get_latest_version(self, process_id):
        cur=self.execute("SELECT v.* FROM process_versions v WHERE v.process_id=? AND NOT EXISTS (SELECT 1 FROM process_versions child WHERE child.parent_version_id=v.version_id) ORDER BY v.created_at DESC,v.version_id DESC LIMIT 1",(process_id,))
        return self._dict(cur.fetchone(),cur)

    def get_rules(self, process_id):
        cur = self.execute("SELECT * FROM rules WHERE process_id=? ORDER BY rule_id", (process_id,)); return [self._dict(x, cur) for x in cur.fetchall()]

    def get_resources(self, process_id):
        cur = self.execute("SELECT * FROM resources WHERE process_id=? ORDER BY resource_id", (process_id,)); return [self._dict(x, cur) for x in cur.fetchall()]

    def get_states(self, process_id):
        cur = self.execute("SELECT * FROM runtime_states WHERE process_id=? ORDER BY state_id", (process_id,)); return [self._dict(x, cur) for x in cur.fetchall()]

    def create_run(self, run_id, process_id, fingerprint, status="running"):
        self.execute("INSERT INTO runs(run_id,process_id,config_fingerprint,status) VALUES(?,?,?,?)", (run_id, process_id, fingerprint, status)); self.connection.commit()

    def update_run_status(self, run_id, status):
        self.execute("UPDATE runs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE run_id=?", (status, run_id)); self.connection.commit()

    def get_run(self, run_id):
        cur = self.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)); return self._dict(cur.fetchone(), cur)

    def append_event(self, run_id, event_type, payload):
        cur = self.execute("SELECT COALESCE(MAX(sequence_no),0)+1 FROM provenance_events WHERE run_id=?", (run_id,)); n=cur.fetchone()[0]
        self.execute("INSERT INTO provenance_events(run_id,sequence_no,event_type,payload_json) VALUES(?,?,?,?)", (run_id,n,event_type,json.dumps(payload,sort_keys=True))); self.connection.commit()

    def save_request(self, run_id, request):
        p=request.to_dict(); self.execute("INSERT INTO requests(request_id,run_id,process_id,source_version_id,operation,raw_text,target_element,payload_json) VALUES(?,?,?,?,?,?,?,?)", (request.request_id,run_id,request.process_id,request.source_version_id,request.operation.value,request.raw_text,request.target_element,json.dumps(p))); self.connection.commit()

    def save_decision(self, run_id, decision):
        self.execute("INSERT INTO decisions(decision_id,run_id,status,reason,payload_json) VALUES(?,?,?,?,?)", (decision.decision_id,run_id,decision.status.value,decision.reason,json.dumps(decision.to_dict()))); self.connection.commit()

    def save_candidate(self, run_id, candidate):
        self.execute("INSERT INTO candidates(candidate_id,run_id,source_version_id,bpmn_xml,checksum,payload_json) VALUES(?,?,?,?,?,?)", (candidate.candidate_id,run_id,candidate.source_version_id,candidate.bpmn_xml,candidate.checksum,json.dumps(candidate.to_dict()))); self.connection.commit()

    def save_experiment(self, run_id, report):
        self.execute("INSERT INTO simulations(report_id,run_id,candidate_id,passed,payload_json) VALUES(?,?,?,?,?)", (report.report_id,run_id,report.candidate_id,int(report.passed),json.dumps(report.to_dict()))); self.connection.commit()

    def add_rag_case(self, evidence_id, run_id, process_id, source_version_id, operation, text, decision, metadata_json):
        run = self.get_run(run_id)
        if not run or run["status"] != "approved":
            raise ApprovalRequired("Only final approved runs may enter RAG")
        self.execute("INSERT INTO rag_cases(evidence_id,run_id,process_id,source_version_id,operation,text,decision,metadata_json,active) VALUES(?,?,?,?,?,?,?,?,1)", (evidence_id,run_id,process_id,source_version_id,operation,text,decision,metadata_json)); self.connection.commit()

    def revoke_rag_case(self, evidence_id, reason):
        self.execute("UPDATE rag_cases SET active=0,revoked_reason=? WHERE evidence_id=?", (reason,evidence_id)); self.connection.commit()

    def list_rag_cases(self, process_id, active_only=False, operation=None, source_version_id=None):
        sql="SELECT * FROM rag_cases WHERE process_id=?"; args=[process_id]
        if active_only: sql += " AND active=1"
        if operation: sql += " AND operation=?"; args.append(operation)
        if source_version_id: sql += " AND (source_version_id=? OR source_version_id IS NULL)"; args.append(source_version_id)
        sql += " ORDER BY evidence_id"
        cur=self.execute(sql,tuple(args)); return [self._dict(x,cur) for x in cur.fetchall()]

    def has_rag_case(self, evidence_id):
        cur=self.execute("SELECT 1 FROM rag_cases WHERE evidence_id=?",(evidence_id,)); return cur.fetchone() is not None

    def save_retrieval_log(self, retrieval_id, run_id, query_hash, filters, scores, ranking, index_version):
        self.execute("INSERT INTO retrieval_logs(retrieval_id,run_id,query_hash,filters_json,scores_json,ranking_json,index_version) VALUES(?,?,?,?,?,?,?)", (retrieval_id,run_id,query_hash,json.dumps(filters,sort_keys=True),json.dumps(scores,sort_keys=True),json.dumps(ranking),index_version)); self.connection.commit()
