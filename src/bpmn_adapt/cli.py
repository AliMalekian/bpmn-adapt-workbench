"""Complete CLI parity for every application use case."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time

from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import ConfigurationError,Settings

EXIT_OK,EXIT_INPUT,EXIT_REJECTED,EXIT_EXTERNAL,EXIT_INTERNAL=0,2,3,4,5


def parser():
    p=argparse.ArgumentParser(prog="bpmn-adapt")
    p.add_argument("--config"); p.add_argument("--json",action="store_true")
    p.add_argument("--seed",type=int); p.add_argument("--run-id")
    mode=p.add_mutually_exclusive_group(); mode.add_argument("--offline",action="store_true"); mode.add_argument("--live",action="store_true")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("gui")
    sub.add_parser("interactive")

    # Providers subcommand
    prov_parser = sub.add_parser("providers")
    prov_sub = prov_parser.add_subparsers(dest="provider_action", required=True)
    prov_sub.add_parser("list")
    p_add = prov_sub.add_parser("add")
    p_add.add_argument("--id", dest="prov_id")
    p_add.add_argument("--name")
    p_add.add_argument("--type", default="openai_compatible")
    p_add.add_argument("--base-url", default="")
    p_add.add_argument("--model", default="")
    p_add.add_argument("--api-key", default="")
    p_add.add_argument("--priority", type=int, default=99)
    p_add.add_argument("--file")
    p_del = prov_sub.add_parser("delete")
    p_del.add_argument("provider_id")
    p_test = prov_sub.add_parser("test")
    p_test.add_argument("provider_id")
    prov_sub.add_parser("test-all")
    p_en = prov_sub.add_parser("enable")
    p_en.add_argument("provider_id")
    p_dis = prov_sub.add_parser("disable")
    p_dis.add_argument("provider_id")
    p_key = prov_sub.add_parser("set-key")
    p_key.add_argument("provider_id")
    p_key.add_argument("api_key")

    # run-manual subcommand
    run_man = sub.add_parser("run-manual")
    run_man.add_argument("--provider", required=True)
    run_man.add_argument("--dataset", required=True)
    run_man.add_argument("--operation", required=True, choices=("ADD", "MODIFY", "REMOVE", "RE_ADD"))
    run_man.add_argument("--target", required=True)
    run_man.add_argument("--request-text", required=True)
    run_man.add_argument("--state-id", default="state_1")

    # run-benchmark subcommand
    run_bm = sub.add_parser("run-benchmark")
    run_bm.add_argument("--dataset-root", required=True)
    run_bm.add_argument("--mode", required=True, choices=("single", "multi", "fallback"))
    run_bm.add_argument("--provider")
    run_bm.add_argument("--providers")
    run_bm.add_argument("--datasets")
    run_bm.add_argument("--request-types", default="REMOVE,MODIFY,ADD,RE_ADD")
    run_bm.add_argument("--repetitions", type=int, default=1)
    run_bm.add_argument("--output", default="experiments/live_evaluation_v4")
    run_bm.add_argument("--screenshot-strategy", choices=("A", "B", "C", "D"), default="B")
    run_bm.add_argument("--allow-synthetic-screenshots", action="store_true")
    run_bm.add_argument("--resume", action="store_true", help="Resume from previous checkpoint")

    # compare-results subcommand
    comp = sub.add_parser("compare-results")
    comp.add_argument("--runs-dir", required=True)

    for name in ("ingest","index-rag","validate","simulate","evaluate","report","baseline","deploy"):
        cmd=sub.add_parser(name); cmd.add_argument("folder")
        if name=="baseline": cmd.add_argument("--variant")
        if name=="deploy": cmd.add_argument("--create-instance",action="store_true"); cmd.add_argument("--variables",default="{}")
    for name in ("analyse","plan","adapt"):
        cmd=sub.add_parser(name); cmd.add_argument("folder"); cmd.add_argument("request")
        cmd.add_argument("--target"); cmd.add_argument("--state")
        if name!="plan": cmd.add_argument("--operation",choices=("ADD","MODIFY","REMOVE","RE_ADD"))
    revoke=sub.add_parser("revoke-rag"); revoke.add_argument("evidence_id"); revoke.add_argument("reason")
    migrate=sub.add_parser("migrate"); migrate.add_argument("instance_id"); migrate.add_argument("target_definition_key"); migrate.add_argument("--mapping",default="{}")
    for name in ("approve","reject"):
        cmd=sub.add_parser(name); cmd.add_argument("approval_run_id"); cmd.add_argument("reason"); cmd.add_argument("--actor",default="user")
    inspect=sub.add_parser("inspect"); inspect.add_argument("folder",nargs="?"); inspect.add_argument("--instance")
    batch=sub.add_parser("batch"); batch.add_argument("folders",nargs="+"); batch.add_argument("--request")
    export=sub.add_parser("export"); export.add_argument("export_run_id"); export.add_argument("destination")
    replay=sub.add_parser("replay"); replay.add_argument("replay_run_id")
    return p


def _settings(args):
    overrides={}
    if args.seed is not None: overrides["evaluation_seed"]=args.seed
    if args.offline: overrides.update(llm_mode="mock",engine_mode="dry_run",vector_backend="local")
    if args.live: overrides["llm_mode"]="live"
    return Settings.load(args.config,overrides=overrides)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    app=None
    try:
        args=parser().parse_args(argv); settings=_settings(args)
        command=args.command
        if command=="gui":
            from bpmn_adapt.gui.app import DesktopApp
            from bpmn_adapt.gui.controller import GuiController
            controller=GuiController.thread_local_factory(lambda: RuntimeAdaptationApplication.from_settings(settings))
            try:
                DesktopApp(controller).mainloop()
            finally:
                controller.close()
            return EXIT_OK

        if command=="interactive":
            from bpmn_adapt.interactive import InteractiveWorkbenchShell
            InteractiveWorkbenchShell().cmdloop()
            return EXIT_OK

        if command=="providers":
            from bpmn_adapt.providers.manager import ProviderManager
            mgr = ProviderManager()
            act = args.provider_action
            if act == "list":
                payload = mgr.list()
            elif act == "add":
                if args.file:
                    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
                else:
                    data = {
                        "id": args.prov_id,
                        "name": args.name or args.prov_id,
                        "type": args.type,
                        "base_url": args.base_url,
                        "model": args.model,
                        "api_key": args.api_key,
                        "priority": args.priority,
                        "enabled": bool(args.api_key),
                    }
                mgr.add(data)
                payload = {"status": "SUCCESS", "message": f"Added provider {data.get('id')}"}
            elif act == "delete":
                mgr.delete(args.provider_id)
                payload = {"status": "SUCCESS", "message": f"Deleted provider {args.provider_id}"}
            elif act == "test":
                payload = mgr.test(args.provider_id)
            elif act == "test-all":
                payload = mgr.test_all()
            elif act == "enable":
                mgr.enable(args.provider_id)
                payload = {"status": "SUCCESS", "message": f"Enabled {args.provider_id}"}
            elif act == "disable":
                mgr.disable(args.provider_id)
                payload = {"status": "SUCCESS", "message": f"Disabled {args.provider_id}"}
            elif act == "set-key":
                mgr.update_api_key_runtime(args.provider_id, args.api_key)
                payload = {"status": "SUCCESS", "message": f"Set API key for {args.provider_id}"}
            else:
                raise ValueError(f"Unknown provider action: {act}")

            print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
            return EXIT_OK

        if command=="compare-results":
            from bpmn_adapt.evaluation.comparison import generate_comparison
            payload = generate_comparison(args.runs_dir)
            print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
            return EXIT_OK

        if command=="run-manual":
            app = RuntimeAdaptationApplication.from_settings(settings)
            res = app.adapt_folder(
                args.dataset,
                args.request_text,
                target=args.target,
                operation=args.operation,
                state_id=args.state_id,
            )
            payload = {
                "decision": res.decision.status.value,
                "rejection_category": res.decision.rejection_category,
                "proposed_timing": getattr(res.decision, "proposed_timing", "current"),
                "rule_ids": list(res.decision.rule_ids),
                "resource_ids": list(res.decision.resource_ids),
                "reason": res.decision.reason,
                "status": res.status,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
            return EXIT_OK

        if command=="run-benchmark":
            from bpmn_adapt.evaluation.benchmark_runner import BenchmarkRunner
            ds_list = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets else None
            p_list = [p.strip() for p in args.providers.split(",") if p.strip()] if args.providers else None
            runner = BenchmarkRunner(
                dataset_root=args.dataset_root,
                mode=args.mode,
                provider=args.provider,
                providers=p_list,
                datasets=ds_list,
                request_types=args.request_types,
                repetitions=args.repetitions,
                output_dir=args.output,
                screenshot_strategy=args.screenshot_strategy,
                allow_synthetic=args.allow_synthetic_screenshots,
                resume=args.resume,
            )
            payload = runner.run()
            print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
            return EXIT_OK

        app=RuntimeAdaptationApplication.from_settings(settings)
        if command=="ingest": payload=app.ingest(args.folder).definition.to_dict()
        elif command=="index-rag": payload=app.index_rag_folder(args.folder)
        elif command=="revoke-rag": payload=app.revoke_rag(args.evidence_id,args.reason)
        elif command=="analyse": payload=app.analyse_folder(args.folder,args.request,target=args.target,operation=args.operation,state_id=args.state).to_dict()
        elif command=="plan": payload=app.plan_folder(args.folder,args.request,target=args.target,state_id=args.state)
        elif command=="adapt": payload=app.adapt_folder(args.folder,args.request,target=args.target,operation=args.operation,state_id=args.state,run_id=args.run_id).to_dict()
        elif command=="validate": payload=app.validate_folder(args.folder)
        elif command=="simulate": payload=app.simulate_folder(args.folder)
        elif command=="deploy": payload=app.deploy_folder(args.folder,run_id=args.run_id,create_instance=args.create_instance,variables=json.loads(args.variables))
        elif command=="migrate": payload=app.migrate_instance(args.instance_id,args.target_definition_key,json.loads(args.mapping),run_id=args.run_id)
        elif command in {"approve","reject"}: payload=app.record_approval(args.approval_run_id,command.upper(),args.reason,args.actor)
        elif command=="inspect": payload=app.inspect(args.folder,args.instance)
        elif command=="evaluate": payload=app.evaluate_folder(args.folder)
        elif command=="baseline": payload=app.baseline_folder(args.folder,args.variant)
        elif command=="batch": payload=app.batch_folders(args.folders,args.request)
        elif command=="report": payload=app.report_folder(args.folder)
        elif command=="export": payload={"archive":str(app.export_run(args.export_run_id,args.destination))}
        elif command=="replay": payload=app.replay_run(args.replay_run_id).to_dict()
        else: raise ValueError(f"Unknown command: {command}")
        print(json.dumps(payload,ensure_ascii=False,indent=None if args.json else 2))
        status=payload.get("status") if isinstance(payload,dict) else None
        return EXIT_REJECTED if status in {"rejected","failed","FAIL","ERROR"} else EXIT_OK
    except (ValueError,FileNotFoundError,ConfigurationError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"ERROR","error_type":type(exc).__name__,"message":str(exc)}),file=sys.stderr)
        return EXIT_INPUT
    except (ConnectionError,TimeoutError) as exc:
        print(json.dumps({"status":"ERROR","error_type":type(exc).__name__,"message":str(exc)}),file=sys.stderr)
        return EXIT_EXTERNAL
    except Exception as exc:
        print(json.dumps({"status":"ERROR","error_type":type(exc).__name__,"message":str(exc)}),file=sys.stderr)
        return EXIT_INTERNAL
    finally:
        if app is not None: app.close()


if __name__=="__main__": raise SystemExit(main())
