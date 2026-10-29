"""Resumable command-line full-dataset evidence runner."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpmn_adapt.config import Settings
from bpmn_adapt.evaluation.datasets import DatasetExecutor,discover_dataset
from bpmn_adapt.evaluation.manifest import ExperimentManifest


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--root",default="."); p.add_argument("--profile",default="config/offline.toml")
    p.add_argument("--resume",default="experiments/full-dataset/manifest.jsonl")
    p.add_argument("--variants",default="none,syntactic,semantic,hybrid")
    p.add_argument("--workers",type=int,default=4); p.add_argument("--json",action="store_true")
    p.add_argument("--scenario-kinds",default="inspect,evaluate,adapt")
    args=p.parse_args(argv); settings=Settings.load(args.profile)
    output=Path(args.resume).resolve().parent
    discovery=discover_dataset(args.root,prefixes=("Camunda-","Pmo-","Mangler-"))
    manifest=ExperimentManifest(Path(args.resume))
    result=DatasetExecutor(settings,manifest,output,args.workers).run(
        discovery.valid,tuple(x for x in args.variants.split(",") if x),
        tuple(x for x in args.scenario_kinds.split(",") if x))
    payload={**result,"valid_folders":len(discovery.valid),"invalid_folders":len(discovery.invalid),
             "invalid":[{"path":str(item.path),"reason":item.reason} for item in discovery.invalid],
             "manifest":str(Path(args.resume).resolve())}
    print(json.dumps(payload,indent=None if args.json else 2)); return 0 if not discovery.invalid else 3


if __name__=="__main__": raise SystemExit(main())
