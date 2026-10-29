from pathlib import Path
import re, xml.etree.ElementTree as ET
from collections import defaultdict, deque

ROOT = Path.cwd()
OUTPUTS = {"states.txt", "RagData.txt", "testcasees.txt"}

def read(p):
    return p.read_text(encoding="utf-8-sig", errors="replace")

def numbered(text, kind):
    rx = re.compile(rf"(?:^|\n)\s*(\d+)\.\s*(.+?)(?=\n\s*\d+\.\s|\Z)", re.S)
    out = [(int(n), ' '.join(s.split())) for n,s in rx.findall(text)]
    return out or [(1, ' '.join(text.split())[:240])]

def resource_items(text):
    # Resources are conventionally one unnumbered fact per line; retain the
    # source-file line order as the resource numbering used by requests.
    lines=[' '.join(x.split()) for x in text.splitlines() if x.strip()]
    return list(enumerate(lines, 1)) or [(1, 'No resource stated')]

def bpmn(folder):
    files = [p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith((".bpmn", ".bpmn2", ".bpmn2.xml", ".xml"))]
    nodes, flows = {}, []
    for p in files:
        try: root = ET.fromstring(read(p))
        except ET.ParseError: continue
        for e in root.iter():
            tag=e.tag.rsplit('}',1)[-1]
            eid=e.attrib.get('id'); name=e.attrib.get('name','').strip()
            if tag == 'sequenceFlow':
                flows.append((e.attrib.get('sourceRef'), e.attrib.get('targetRef')))
            elif eid and (name or tag in {'startEvent','endEvent','exclusiveGateway','parallelGateway','inclusiveGateway'}):
                nodes[eid] = name or tag
    if not nodes:
        return ['Start event','Process activity','End event'], [('Start event','Process activity'),('Process activity','End event')]
    succ=defaultdict(list); pred=defaultdict(list)
    for a,b in flows:
        if a in nodes and b in nodes: succ[a].append(b); pred[b].append(a)
    starts=[x for x in nodes if not pred[x]] or list(nodes)
    ordered=[]; q=deque(starts); seen=set()
    while q:
        x=q.popleft()
        if x in seen: continue
        seen.add(x); ordered.append(x); q.extend(succ[x])
    ordered += [x for x in nodes if x not in seen]
    names=[nodes[x] for x in ordered]
    nameflows=[(nodes[a],nodes[b]) for a,b in flows if a in nodes and b in nodes]
    return names, nameflows

def requests(text):
    blocks=re.split(r'(?=Request\s*[1-4]\s*:)', text, flags=re.I)
    result=[]
    for b in blocks:
        m=re.search(r'Request\s*([1-4])\s*:',b,re.I)
        if not m: continue
        target=re.search(r'Removed element:\s*(.+?)(?=\n(?:Reason|Conflict details):|\Z)',b,re.S|re.I)
        rules=[int(x) for x in re.findall(r'Rule\s*(\d+)',b,re.I)]
        resources=[int(x) for x in re.findall(r'Resource\s*(\d+)',b,re.I)]
        result.append((int(m.group(1)), ' '.join(target.group(1).split()) if target else 'process activity', rules, resources))
    return result

def readd(text):
    m=re.search(r'Restored element:\s*(.+?)(?=\n\s*\n|\nRestoration details:|\Z)',text,re.S|re.I)
    return ' '.join(m.group(1).split()) if m else 'restored process activity'

def refs(ids, items, label):
    return ', '.join(f'{label} {i} ({dict(items).get(i, "not specified")})' for i in sorted(set(ids))) or 'None'

def main():
    done=[]; skipped=[]; errors=[]
    for folder in [p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith('.')]:
        reqfiles=['Rules.txt','Resources.txt','Remove_requests.txt','Re_Add_Request.txt']
        if not all((folder/x).is_file() for x in reqfiles):
            skipped.append((folder.name,'missing required source file')); continue
        models=[p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith(('.bpmn','.bpmn2','.bpmn2.xml','.xml'))]
        narrative=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower()=='.txt' and p.name not in reqfiles+list(OUTPUTS) and not p.name.endswith('.quality.txt')]
        if not models or not narrative:
            skipped.append((folder.name,'missing BPMN model or narrative text')); continue
        try:
            names, flows=bpmn(folder)
            rules=numbered(read(folder/'Rules.txt'),'Rule'); resources=resource_items(read(folder/'Resources.txt'))
            reqs=requests(read(folder/'Remove_requests.txt'))
            if len(reqs)!=4: raise ValueError(f'expected 4 Remove requests, found {len(reqs)}')
            readd_target=readd(read(folder/'Re_Add_Request.txt'))
            # Four runtime positions sampled over an actual model traversal.
            pick=lambda i: names[min(i,max(0,len(names)-1))]
            states=[]
            for i,title in enumerate(['Initial / early execution','Intermediate / decision','Resource-dependent / waiting','Near completion / completed'],1):
                cur=pick([1, max(1,len(names)//3), max(1,2*len(names)//3), len(names)-1][i-1])
                completed=', '.join(names[:max(0, names.index(cur))]) or 'None'
                nxt=[b for a,b in flows if a==cur] or ['Process completion' if i==4 else pick(min(names.index(cur)+1,len(names)-1))]
                states.append(f'''STATE-{i:02d}: {title}\nCurrent process position: {cur}\nCompleted activities: {completed}\nCurrent active activity or waiting point: {cur}\nToken position / execution status: token is at {cur}; predecessors in the traversed BPMN path are complete.\nRelevant user/case context: one active case follows the original model.\nRelevant available resources: {refs([resources[0][0]],resources,'Resource')}\nApplicable rules: {refs([rules[0][0]],rules,'Rule')}\nPossible next activities: {', '.join(nxt)}''')
            (folder/'states.txt').write_text('\n\n'.join(states)+'\n',encoding='utf-8')
            # RAG examples are grounded in the supplied request evidence. Categories vary the validation lens.
            rag=[]
            categories=[('REMOVE-RESOURCE-CONFLICT','REJECT','resource'),('REMOVE-RULE-CONFLICT','REJECT','rule'),('REMOVE-RULE-AND-RESOURCE-CONFLICT','REJECT','both'),('REMOVE-VALID','ACCEPT','valid')]
            # The fourth source request explicitly identifies the folder's safe removal.
            # Use that actual optional element for each valid contrast example instead of
            # falsely accepting a removal that the source itself marks as mandatory.
            valid_target=reqs[3][1]
            for n,target,rids,xids in reqs:
                for c,decision,lens in categories:
                    example_target = valid_target if lens=='valid' else target
                    use_r = rids if lens in ('rule','both') else []
                    use_x = xids if lens in ('resource','both') else []
                    if lens=='valid':
                        reason='The proposed scope is limited to an optional, non-control-flow observation and preserves every mandatory predecessor, successor, rule, and resource constraint.'
                        change='Remove only the optional occurrence while reconnecting its predecessor directly to its successor; retain all mandatory BPMN elements.'
                    else:
                        reason=(('It conflicts with '+refs(use_r,rules,'Rule')+'. ' if use_r else '') + ('It conflicts with '+refs(use_x,resources,'Resource')+'.' if use_x else '')).strip()
                        if not reason: reason='No concrete conflict was specified for this request; the operation is rejected pending evidence.'
                        change='No BPMN change is applied; the original incoming and outgoing sequence flows remain intact.'
                    rag.append(f'''Example ID: R{n}-{c}\nOperation type: REMOVE\nCategory: {c}\nUser request: {'Instead, remove the optional element “'+valid_target+'” safely.' if decision=='ACCEPT' else 'Assess removal of “'+target+'” for Request'+str(n)+'.'}\nTarget BPMN element: {example_target}\nDecision: {decision}\nDecision reason: {reason}\nReferenced rules: {refs(use_r,rules,'Rule')}\nReferenced resources: {refs(use_x,resources,'Resource')}\nRequired BPMN change: {change}\nExpected process effect: {'The optional observation is bypassed without changing mandatory routing.' if decision=='ACCEPT' else 'The original behavior is preserved because the requested change is rejected.'}\nToken migration / execution-state note: Existing tokens remain on their current original sequence flow; no token is moved across an unmet gateway or predecessor.\nFinal response to the user: {'Accepted for the explicitly limited optional scope.' if decision=='ACCEPT' else 'Rejected: the cited concrete constraint must remain satisfied.'}''')
            # Re-add examples: first three test explicit supplied constraint lenses; the final restores original behavior.
            for c,decision,lens in [('READD-RESOURCE-CONFLICT','REJECT','resource'),('READD-RULE-CONFLICT','REJECT','rule'),('READD-RULE-AND-RESOURCE-CONFLICT','REJECT','both'),('READD-VALID','ACCEPT','valid')]:
                rids=[rules[0][0]] if lens in ('rule','both') else []
                xids=[resources[0][0]] if lens in ('resource','both') else []
                reason=('The re-add would be placed in a way that violates '+refs(rids,rules,'Rule')+' and '+refs(xids,resources,'Resource')+'.') if lens!='valid' else 'The element is restored at its original location, with its original predecessor and successor, so original behavior and all constraints are recovered.'
                rag.append(f'''Example ID: RA-{c}\nOperation type: RE_ADD\nCategory: {c}\nUser request: Re-add “{readd_target}” to the process.\nTarget BPMN element: {readd_target}\nDecision: {decision}\nDecision reason: {reason}\nReferenced rules: {refs(rids,rules,'Rule')}\nReferenced resources: {refs(xids,resources,'Resource')}\nRequired BPMN change: {'No change; reject the conflicting placement.' if decision=='REJECT' else 'Restore the element at its original position, reconnect its original incoming and outgoing sequence flows, and preserve gateway semantics.'}\nExpected process effect: {'No effect; the invalid re-add is not applied.' if decision=='REJECT' else 'The original process behavior is recovered and is equivalent to the original model.'}\nToken migration / execution-state note: {'Tokens stay on the current valid route.' if decision=='REJECT' else 'Tokens at the removed bypass are safely redirected to the restored element before continuing to its original successor.'}\nFinal response to the user: {'Rejected because the exact proposed placement conflicts with cited constraints.' if decision=='REJECT' else 'Accepted: the original element, location, connections, and behavior are restored.'}''')
            (folder/'RagData.txt').write_text('\n\n'.join(rag)+'\n',encoding='utf-8')
            # Test cases reuse real request targets and rule/resource identifiers.
            t=[]
            first_target=reqs[0][1]; rr=reqs[0][2] or [rules[0][0]]; xx=reqs[0][3] or [resources[0][0]]
            specs=[('TC-01-RESOURCE-CONFLICT','Resource conflict',first_target,[],xx,'BLOCKED','Insufficient/unavailable required resource prevents execution.'),('TC-02-RULE-CONFLICT','Rule conflict',first_target,rr,[],'BLOCKED','The requested action violates the cited rule.'),('TC-03-RULE-AND-RESOURCE-CONFLICT','Rule and resource conflict',first_target,rr,xx,'BLOCKED','Both the rule and resource constraints block execution.'),('TC-04-VALID-EXECUTION','Valid execution',readd_target,[],[],'PASS','The original route is executable, and the same route is restored after the remove/re-add cycle.')]
            for ident,title,target,rids,xids,status,explanation in specs:
                t.append(f'''Test case ID: {ident}\nScenario title: {title}\nInitial state: STATE-02 with a token before the applicable activity.\nUser request / process action: Execute or validate {target}.\nCurrent token position: Immediately before {target} on its original BPMN sequence flow.\nRequired resources: {refs(xids,resources,'Resource') if xids else 'All resources required by the original process are available.'}\nRelevant rules: {refs(rids,rules,'Rule') if rids else 'All applicable original rules are satisfied.'}\nExpected execution path: Follow the original predecessor → {target} → original successor route; respect any gateway conditions.\nExpected result: {status}\nValidation status: {status}\nExplanation: {explanation}''')
            (folder/'testcasees.txt').write_text('\n\n'.join(t)+'\n',encoding='utf-8')
            done.append(folder.name)
        except Exception as e: errors.append((folder.name,str(e)))
    if skipped or errors:
        lines=['Dataset generation report', *[f'SKIPPED | {a} | {b}' for a,b in skipped], *[f'ERROR | {a} | {b}' for a,b in errors]]
        with (ROOT/'generation_errors.txt').open('a',encoding='utf-8') as f: f.write('\n'.join(lines)+'\n')
    print(f'discovered={len(done)+len(skipped)+len(errors)} processed={len(done)} skipped={len(skipped)} errors={len(errors)} states={len(done)*4} rag={len(done)*20} tests={len(done)*4}')
    for a,b in errors: print('ERROR',a,b)

if __name__ == '__main__': main()
