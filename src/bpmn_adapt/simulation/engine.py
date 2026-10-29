"""Bounded graph-state simulation for BPMN control-flow validation."""
from __future__ import annotations
from bpmn_adapt.bpmn.graph import BpmnGraph


def simulate(xml:str,max_steps:int|None=None,max_states:int=10_000)->tuple[tuple[tuple[str,...],...],tuple[dict,...]]:
    graph=BpmnGraph.from_xml(xml)
    starts=[n.element_id for n in graph.nodes.values() if n.kind=="startEvent"] or [n for n in graph.nodes if not graph.predecessors(n)]
    ends={n.element_id for n in graph.nodes.values() if n.kind=="endEvent"}
    limit=max_steps or max(10,len(graph.nodes)*4)
    completed=[]; failures=[]
    agenda=[((s,),(s,)) for s in starts]
    explored=0
    visited=set()
    while agenda:
        if explored>=max_states:
            failures.append({"type":"state_limit","max_states":max_states}); break
        tokens,path=agenda.pop()
        marking=tuple(sorted(tokens))
        if marking in visited: continue
        visited.add(marking)
        explored+=1
        if len(path)>=limit:
            failures.append({"type":"step_limit","tokens":tokens,"path":path}); continue
        transitions=[]
        handled_parallel_joins=set()
        for index,node_id in enumerate(tokens):
            node=graph.nodes.get(node_id)
            if not node: continue
            predecessors=graph.predecessors(node_id); successors=graph.successors(node_id)
            if node_id in ends:
                next_tokens=tokens[:index]+tokens[index+1:]
                transitions.append((next_tokens,path+(node_id,)))
                continue
            is_parallel=node.kind=="parallelGateway"
            if is_parallel and len(predecessors)>1:
                if node_id in handled_parallel_joins: continue
                handled_parallel_joins.add(node_id)
                positions=[i for i,x in enumerate(tokens) if x==node_id]
                if len(positions)<len(predecessors): continue
                remove=set(positions[:len(predecessors)])
                remaining=tuple(x for i,x in enumerate(tokens) if i not in remove)
                spawned=successors if len(successors)>1 else successors[:1]
                transitions.append((tuple(sorted(remaining+spawned)),path+(node_id,)))
                continue
            remaining=tokens[:index]+tokens[index+1:]
            if is_parallel and len(successors)>1:
                transitions.append((tuple(sorted(remaining+successors)),path+(node_id,)))
            else:
                for nxt in successors: transitions.append((tuple(sorted(remaining+(nxt,))),path+(node_id,)))
        if not transitions:
            if not tokens: completed.append(path)
            else: failures.append({"type":"deadlock","tokens":tokens,"path":path})
        for next_tokens,next_path in transitions:
            if not next_tokens: completed.append(next_path)
            else: agenda.append((next_tokens,next_path))
    if not starts: failures.append({"type":"no_start"})
    if not completed: failures.append({"type":"no_completion"})
    return tuple(completed),tuple(failures)
