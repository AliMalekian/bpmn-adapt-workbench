"""Capture a deterministic Windows GUI evidence screenshot without live services."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpmn_adapt.gui.app import DesktopApp


class EvidenceController:
    """The screenshot does not execute use cases; production controller is used normally."""


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument("output",type=Path)
    parser.add_argument("--all-panels",action="store_true"); args=parser.parse_args(argv)
    from PIL import ImageGrab
    app=DesktopApp(EvidenceController()); app.folder.set("<select any valid process folder>")
    app.request.set("Remove or modify an activity"); app.update_idletasks(); app.update()
    x,y=app.winfo_rootx(),app.winfo_rooty(); width,height=app.winfo_width(),app.winfo_height()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    bbox=(x,y,x+width,y+height)
    ImageGrab.grab(bbox=bbox,all_screens=True).save(args.output)
    if args.all_panels:
        sample={"run_id":"defense-demo","status":"approved","process_id":"example",
                "rules":[{"rule_id":"R1","status":"satisfied"}],
                "resources":[{"resource_id":"RES1","available":True}],
                "filters":{"process_id":"example","operation":"REMOVE","active":True},
                "hits":[{"evidence_id":"E1","semantic":.83,"syntactic":.71,"final":.79}],
                "selected_plan":{"strategy":"forward","cost":{"time":.2,"budget":.1,"risk":.1}},
                "diff":{"removed_nodes":["Task_1"]},"migration":{"Task_1":"Task_2"},
                "traces":[["Start","Task_2","End"]],"failures":[],
                "statistics":{"hybrid_vs_none":{"p_value":.04}},
                "approval":{"actor":"researcher","decision":"APPROVE"},
                "archive":"defense-demo.zip","checksums":{"result.json":"sha256"}}
        for name,panel in app.panels.items():
            panel.display(sample); app.notebook.select(panel); app.update_idletasks(); app.update()
            safe="".join(character.lower() if character.isalnum() else "-" for character in name).strip("-")
            ImageGrab.grab(bbox=bbox,all_screens=True).save(args.output.parent/f"panel-{safe}.png")
    app.worker.shutdown(); app.destroy(); return 0


if __name__=="__main__": raise SystemExit(main())
