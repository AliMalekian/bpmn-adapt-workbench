from __future__ import annotations
import unittest

from bpmn_adapt.engine.camunda8 import Camunda8EngineAdapter
from bpmn_adapt.engine.contracts import EngineAdapterError
from bpmn_adapt.engine.http import HttpResponse
from tests.unit.test_bpmn_semantics import VALID


class Transport:
    def __init__(self): self.calls=[]; self.instances={}
    def request(self, method, path, **kwargs):
        self.calls.append((method,path,kwargs))
        if path=="/v2/topology": return HttpResponse(200,{"version":"8.8.0"},{})
        if path=="/v2/deployments": return HttpResponse(200,{"deploymentKey":"d1","tenantId":"t","deployments":[{"processDefinition":{"processDefinitionKey":"pd1","processDefinitionId":"Process_1"}}]}, {})
        if path=="/v2/process-instances":
            self.instances["i1"]={"processDefinitionKey":"pd1","activeElementIds":["start"],"variables":kwargs["json"]["variables"],"state":"ACTIVE"}
            return HttpResponse(200,{"processInstanceKey":"i1"},{})
        if path=="/v2/process-instances/search":
            key=str(kwargs["json"]["filter"]["processInstanceKey"]); return HttpResponse(200,{"items":[self.instances[key]]},{})
        if path.endswith("/migration"):
            self.instances["i1"]["processDefinitionKey"]=kwargs["json"]["targetProcessDefinitionKey"]; return HttpResponse(204,{}, {})
        if method=="DELETE": return HttpResponse(204,{}, {})
        raise AssertionError((method,path))


class CamundaRecordingTests(unittest.TestCase):
    def test_success_duplicate_retry_migration_and_cleanup_scope(self):
        transport=Transport(); engine=Camunda8EngineAdapter(transport)
        dep=engine.deploy(VALID,"run","same"); self.assertEqual(dep,engine.deploy(VALID,"run","same"))
        instance=engine.create_instance(dep.process_definition_key,{"_adapt_run_id":"run"},"create")
        receipt=engine.migrate(instance.instance_id,dep.process_definition_key,{"start":"start"},"migrate")
        self.assertEqual(receipt,engine.migrate(instance.instance_id,dep.process_definition_key,{"start":"start"},"migrate"))
        self.assertEqual(engine.cleanup("other").deleted_ids,())
        self.assertEqual(engine.cleanup("run").deleted_ids,("i1",))

    def test_auth_failure_is_not_swallowed(self):
        class Auth:
            def request(self,*args,**kwargs): raise EngineAdapterError("denied",code="ENGINE_AUTH")
        with self.assertRaisesRegex(EngineAdapterError,"denied"):
            Camunda8EngineAdapter(Auth()).deploy(VALID,"r","k")

    def test_timeout_after_deploy_reconciles_remote_definition(self):
        class TimeoutThenFound(Transport):
            def request(self,method,path,**kwargs):
                if path=="/v2/deployments": raise EngineAdapterError("timeout",code="ENGINE_TIMEOUT",retryable=True)
                if path=="/v2/process-definitions/search": return HttpResponse(200,{"items":[{"deploymentKey":"d","processDefinitionKey":"pd","processDefinitionId":"Process_1"}]},{})
                return super().request(method,path,**kwargs)
        self.assertEqual(Camunda8EngineAdapter(TimeoutThenFound()).deploy(VALID,"r","k").process_definition_key,"pd")


if __name__ == "__main__": unittest.main()
