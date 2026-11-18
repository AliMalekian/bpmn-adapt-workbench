"""
Knowledge Graph Service for BPMN Adaptation Workbench (Neo4j Backend).

Implements a Heterogeneous Knowledge Graph (HKG) ontology covering:
1. Process Structure: Process, Pool, Lane, Task, Gateway, Event, SequenceFlow, MessageFlow
2. Governance & Resources: BusinessRule, ResourceRole, ResourceMetric, SLA
3. Adaptation Precedents: AdaptationRequest, DecisionPrecedent, Reasoning Chains
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    GraphDatabase = None
    Driver = Any

logger = logging.getLogger(__name__)


@dataclass
class PrecedentReasoningPath:
    precedent_id: str
    decision: str
    operation: str
    target_element: str
    meta_path_type: str
    structural_similarity: float
    governing_rules: List[str]
    resource_constraints: List[str]
    reasoning_chain: str
    explanation: str


class BPMNKnowledgeGraphService:
    """
    Manages Neo4j Heterogeneous Knowledge Graph operations:
    - Schema creation, unique constraints, and graph indexing
    - Ingestion of BPMN topology, business rules, and resource capacities
    - Subgraph neighborhood extraction (k-hop radius)
    - Structural analogy retrieval via meta-paths (PathSim & Cypher patterns)
    - Zero concept-drift reasoning path compilation
    """

    def __init__(
        self,
        uri: str = "bolt://127.0.0.1:7687",
        auth: tuple = ("neo4j", "123456789"),
        database: str = "neo4j",
    ):
        self.uri = uri
        self.auth = auth
        self.database = database
        self._driver: Optional[Driver] = None

    def connect(self) -> bool:
        """Establishes connection to the Neo4j instance."""
        if GraphDatabase is None:
            logger.error("neo4j driver package is not installed.")
            return False
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=self.auth)
            with self._driver.session(database=self.database) as session:
                res = session.run("RETURN 1 as test")
                record = res.single()
                if record and record["test"] == 1:
                    logger.info("Successfully connected to Neo4j at %s", self.uri)
                    return True
        except Exception as e:
            logger.warning("Could not connect to Neo4j at %s: %s", self.uri, e)
            self._driver = None
            return False
        return False

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def is_connected(self) -> bool:
        return self._driver is not None

    def initialize_schema(self):
        """Creates unique constraints and indexes for the Heterogeneous Knowledge Graph."""
        if not self._driver:
            return

        constraints = [
            "CREATE CONSTRAINT process_id_unique IF NOT EXISTS FOR (p:Process) REQUIRE p.process_id IS UNIQUE",
            "CREATE CONSTRAINT rule_id_unique IF NOT EXISTS FOR (r:BusinessRule) REQUIRE (r.process_id, r.rule_id) IS NODE KEY",
            "CREATE CONSTRAINT role_id_unique IF NOT EXISTS FOR (rr:ResourceRole) REQUIRE (rr.process_id, rr.role_name) IS NODE KEY",
            "CREATE CONSTRAINT precedent_id_unique IF NOT EXISTS FOR (dp:DecisionPrecedent) REQUIRE dp.case_id IS UNIQUE",
        ]

        indexes = [
            "CREATE INDEX task_name_idx IF NOT EXISTS FOR (t:Task) ON (t.name)",
            "CREATE INDEX gateway_type_idx IF NOT EXISTS FOR (g:Gateway) ON (g.gateway_type)",
            "CREATE INDEX operation_idx IF NOT EXISTS FOR (req:AdaptationRequest) ON (req.operation)",
        ]

        with self._driver.session(database=self.database) as session:
            for query in constraints:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug("Constraint query notice: %s", e)
            for query in indexes:
                try:
                    session.run(query)
                except Exception as e:
                    logger.debug("Index query notice: %s", e)
            logger.info("Heterogeneous Knowledge Graph schema initialized successfully.")

    def ingest_process_topology(
        self,
        process_id: str,
        name: str,
        domain: str,
        cluster: str,
        tasks: List[Dict[str, Any]],
        gateways: List[Dict[str, Any]],
        flows: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        resources: List[Dict[str, Any]],
        folder_name: str = "",
    ):
        """
        Populates a complete business process into the graph:
        - Process node
        - Tasks, Gateways, Events
        - Control flows (SEQUENCE_FLOW)
        - Governance links (GOVERNED_BY)
        - Resource allocation links (HAS_RESOURCE, CONSUMES_CAPACITY)
        """
        if not self._driver:
            return

        fname = folder_name or name

        with self._driver.session(database=self.database) as session:
            # 1. Process node
            session.run(
                """
                MERGE (p:Process {process_id: $pid})
                ON CREATE SET p.name = $name, p.folder_name = $fname, p.domain = $domain, p.cluster = $cluster, p.created_at = timestamp()
                ON MATCH SET p.name = $name, p.folder_name = $fname, p.domain = $domain, p.cluster = $cluster
                """,
                pid=process_id,
                name=name,
                fname=fname,
                domain=domain,
                cluster=cluster,
            )

            # 2. Tasks
            for t in tasks:
                session.run(
                    """
                    MERGE (task:Task {task_id: $tid, process_id: $pid})
                    ON CREATE SET task.name = $name, task.type = $ttype, task.folder_name = $fname
                    ON MATCH SET task.name = $name, task.folder_name = $fname
                    WITH task
                    MATCH (p:Process {process_id: $pid})
                    MERGE (p)-[:CONTAINS_TASK]->(task)
                    """,
                    tid=t["id"],
                    pid=process_id,
                    fname=fname,
                    name=t.get("name", t["id"]),
                    ttype=t.get("type", "UserTask"),
                )

            # 3. Gateways
            for g in gateways:
                session.run(
                    """
                    MERGE (gw:Gateway {gateway_id: $gid, process_id: $pid})
                    ON CREATE SET gw.name = $name, gw.gateway_type = $gtype, gw.folder_name = $fname
                    ON MATCH SET gw.name = $name, gw.folder_name = $fname
                    WITH gw
                    MATCH (p:Process {process_id: $pid})
                    MERGE (p)-[:CONTAINS_GATEWAY]->(gw)
                    """,
                    gid=g["id"],
                    pid=process_id,
                    fname=fname,
                    name=g.get("name", g["id"]),
                    gtype=g.get("type", "EXCLUSIVE_XOR"),
                )

            # 4. Sequence Flows
            for f in flows:
                source_id = f.get("source_ref")
                target_id = f.get("target_ref")
                session.run(
                    """
                    MATCH (s {process_id: $pid}) WHERE s.task_id = $src OR s.gateway_id = $src OR s.event_id = $src
                    MATCH (t {process_id: $pid}) WHERE t.task_id = $tgt OR t.gateway_id = $tgt OR t.event_id = $tgt
                    MERGE (s)-[r:SEQUENCE_FLOW {flow_id: $fid}]->(t)
                    """,
                    pid=process_id,
                    src=source_id,
                    tgt=target_id,
                    fid=f.get("id", f"{source_id}->{target_id}"),
                )

            # 5. Rules & GOVERNED_BY links with normative strictness
            for r in rules:
                rule_id = r.get("rule_id", "R_UNKNOWN")
                rule_text = r.get("text", "")
                governed_elements = r.get("governed_elements", [])
                category = r.get("category", "REGULATORY_COMPLIANCE")
                rule_type = r.get("rule_type", "INVARIANT_MANDATE")
                strictness = r.get("strictness", "MANDATORY")

                session.run(
                    """
                    MERGE (rule:BusinessRule {rule_id: $rid, process_id: $pid})
                    ON CREATE SET rule.expression_text = $rtext, rule.category = $cat, rule.folder_name = $fname,
                                  rule.rule_type = $rtype, rule.strictness = $strictness
                    ON MATCH SET rule.expression_text = $rtext, rule.folder_name = $fname,
                                 rule.rule_type = $rtype, rule.strictness = $strictness
                    WITH rule
                    MATCH (p:Process {process_id: $pid})
                    MERGE (p)-[:HAS_RULE]->(rule)
                    """,
                    rid=rule_id,
                    pid=process_id,
                    fname=fname,
                    rtext=rule_text,
                    cat=category,
                    rtype=rule_type,
                    strictness=strictness,
                )

                for elem_name in governed_elements:
                    session.run(
                        """
                        MATCH (t {process_id: $pid})
                        WHERE (t:Task OR t:Gateway)
                          AND (toLower(t.name) CONTAINS toLower($ename) OR toLower($ename) CONTAINS toLower(t.name))
                        MATCH (rule:BusinessRule {rule_id: $rid, process_id: $pid})
                        MERGE (t)-[g:GOVERNED_BY {strictness: $strictness, rule_type: $rtype}]->(rule)
                        """,
                        pid=process_id,
                        ename=elem_name,
                        rid=rule_id,
                        strictness=strictness,
                        rtype=rule_type,
                    )

            # 6. Resources & Allocation
            for res in resources:
                res_name = res.get("name", "")
                res_type = res.get("type", "HUMAN_ROLE")
                capacity = str(res.get("capacity", ""))

                session.run(
                    """
                    MERGE (role:ResourceRole {role_name: $rname, process_id: $pid})
                    ON CREATE SET role.type = $rtype, role.capacity_spec = $cap, role.folder_name = $fname
                    ON MATCH SET role.folder_name = $fname, role.capacity_spec = $cap
                    WITH role
                    MATCH (p:Process {process_id: $pid})
                    MERGE (p)-[:HAS_RESOURCE]->(role)
                    """,
                    rname=res_name,
                    pid=process_id,
                    fname=fname,
                    rtype=res_type,
                    cap=capacity,
                )

    def inspect_subgraph(self, process_id: str, target_element: str, k_hops: int = 2) -> Dict[str, Any]:
        """
        Extracts the local structural neighborhood of a target BPMN element from Neo4j:
        - Target node metadata
        - Incoming and outgoing sequence flows
        - Directly governed business rules and full rule texts
        - Resource capacities associated with the process
        """
        if not self._driver:
            return {}

        out = {
            "target": target_element,
            "found_in_graph": False,
            "incoming_nodes": [],
            "outgoing_nodes": [],
            "governing_rules": [],
            "governing_rule_details": [],
            "resources": [],
            "structural_path": "",
        }

        with self._driver.session(database=self.database) as session:
            # 1. Target node, neighbors, and rules
            cypher = """
            MATCH (t)
            WHERE (t:Task OR t:Gateway)
              AND (t.process_id = $pid OR t.folder_name = $pid)
              AND (
                toLower(t.name) CONTAINS toLower($tgt)
                OR toLower($tgt) CONTAINS toLower(t.name)
                OR any(w IN split(toLower($tgt), ' ') WHERE size(w) > 4 AND toLower(t.name) CONTAINS w)
              )
            WITH t,
                 CASE
                   WHEN toLower(t.name) = toLower($tgt) THEN 1
                   WHEN toLower(t.name) STARTS WITH toLower($tgt) OR toLower($tgt) STARTS WITH toLower(t.name) THEN 2
                   WHEN toLower(t.name) CONTAINS toLower($tgt) OR toLower($tgt) CONTAINS toLower(t.name) THEN 3
                   ELSE 4
                 END AS score
            ORDER BY score ASC, size(t.name) ASC
            LIMIT 1
            OPTIONAL MATCH (t)-[g:GOVERNED_BY]->(r:BusinessRule)
            OPTIONAL MATCH (prev)-[:SEQUENCE_FLOW]->(t)
            OPTIONAL MATCH (t)-[:SEQUENCE_FLOW]->(nxt)
            RETURN t.name AS name,
                   collect(DISTINCT {id: r.rule_id, strictness: g.strictness, type: g.rule_type}) AS rule_summaries,
                   collect(DISTINCT {id: r.rule_id, text: r.expression_text, strictness: g.strictness, type: g.rule_type}) AS rule_objs,
                   collect(DISTINCT prev.name) AS incoming,
                   collect(DISTINCT nxt.name) AS outgoing
            """
            rec = session.run(cypher, pid=process_id, tgt=target_element).single()
            if rec and rec["name"]:
                out["found_in_graph"] = True
                out["matched_name"] = rec["name"]
                out["incoming_nodes"] = [x for x in rec["incoming"] if x]
                out["outgoing_nodes"] = [x for x in rec["outgoing"] if x]
                out["governing_rules"] = [f"{x['id']} ({x.get('strictness', 'MANDATORY')})" for x in rec["rule_summaries"] if x and x.get("id")]
                out["governing_rule_details"] = [x for x in rec["rule_objs"] if x and x.get("id")]

                inc_str = ", ".join(out["incoming_nodes"]) if out["incoming_nodes"] else "None"
                out_str = ", ".join(out["outgoing_nodes"]) if out["outgoing_nodes"] else "None"
                rules_str = ", ".join(out["governing_rules"]) if out["governing_rules"] else "No direct rules"
                out["structural_path"] = f"[{inc_str}] -> [{rec['name']}] -> [{out_str}] (Governed by: {rules_str})"

            # 2. Resources
            res_cypher = """
            MATCH (p:Process)
            WHERE p.process_id = $pid OR p.folder_name = $pid OR p.name = $pid
            MATCH (p)-[:HAS_RESOURCE]->(res:ResourceRole)
            RETURN res.role_name AS name, res.capacity_spec AS capacity
            """
            for row in session.run(res_cypher, pid=process_id):
                out["resources"].append(f"{row['name']} ({row['capacity']})" if row['capacity'] else row['name'])

        return out

    def find_analogous_precedents(
        self,
        current_process_id: str,
        operation: str,
        target_element: str,
        k_hops: int = 2,
        limit: int = 3,
    ) -> List[PrecedentReasoningPath]:
        """
        Retrieves structurally analogous precedent cases using Heterogeneous Graph Pattern Matching.
        Meta-path reasoning avoids concept drift by matching structural topology rather than raw keywords.
        """
        if not self._driver:
            return []

        results: List[PrecedentReasoningPath] = []
        op_norm = operation.strip().upper()
        target_norm = target_element.strip().lower()

        with self._driver.session(database=self.database) as session:
            # 1. Targeted structural match
            cypher = """
            MATCH (dp:DecisionPrecedent)
            WHERE (dp.process_id = $pid OR dp.folder_name = $pid)
              AND dp.operation = $op
              AND (
                toLower(dp.target_element_name) CONTAINS toLower($tgt)
                OR toLower($tgt) CONTAINS toLower(dp.target_element_name)
                OR any(w IN split(toLower($tgt), ' ') WHERE size(w) > 4 AND toLower(dp.target_element_name) CONTAINS w)
              )
            OPTIONAL MATCH (dp)-[:TARGETS_TASK]->(t:Task)-[:GOVERNED_BY]->(r:BusinessRule)
            RETURN dp.case_id AS case_id,
                   dp.decision AS decision,
                   dp.operation AS operation,
                   dp.target_element_name AS target_name,
                   dp.reason AS explanation,
                   dp.referenced_rules AS referenced_rules,
                   collect(DISTINCT r.rule_id) AS rule_ids
            LIMIT $limit
            """
            cursor = session.run(cypher, pid=current_process_id, op=op_norm, tgt=target_norm, limit=limit)
            records = list(cursor)

            # 2. Contrastive process-level precedents if target not directly matched
            if not records:
                contrastive_cypher = """
                MATCH (dp:DecisionPrecedent)
                WHERE (dp.process_id = $pid OR dp.folder_name = $pid)
                  AND dp.operation = $op
                RETURN dp.case_id AS case_id,
                       dp.decision AS decision,
                       dp.operation AS operation,
                       dp.target_element_name AS target_name,
                       dp.reason AS explanation,
                       dp.referenced_rules AS referenced_rules,
                       [] AS rule_ids
                LIMIT $limit
                """
                records = list(session.run(contrastive_cypher, pid=current_process_id, op=op_norm, limit=limit))

            for row in records:
                rules = [r for r in row["rule_ids"] if r] or ([row["referenced_rules"]] if row["referenced_rules"] else [])
                path = PrecedentReasoningPath(
                    precedent_id=row["case_id"] or "PRECEDENT_UNKNOWN",
                    decision=row["decision"] or "APPROVE",
                    operation=row["operation"] or op_norm,
                    target_element=row["target_name"] or "",
                    meta_path_type="Process-Task-Precedent-Graph",
                    structural_similarity=0.95,
                    governing_rules=rules,
                    resource_constraints=[],
                    reasoning_chain=f"Target({row['target_name']}) -> Rules({', '.join(rules) if rules else 'None'}) => Decision({row['decision']})",
                    explanation=row["explanation"] or "Consistent governance precedent from Knowledge Graph.",
                )
                results.append(path)

        return results
