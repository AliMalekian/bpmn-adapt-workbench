"""Publication-ready evaluation artefacts and checksum manifest."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


class EvidenceWriter:
    def write(self, output_dir: Path, observations: list[dict], statistics: dict,
              metadata: dict):
        output_dir.mkdir(parents=True,exist_ok=True)
        raw_json=output_dir/"observations.json"
        raw_json.write_text(json.dumps(observations,indent=2,sort_keys=True),encoding="utf-8")
        fields=sorted({key for row in observations for key in row})
        with (output_dir/"observations.csv").open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader()
            for row in observations: writer.writerow({key:_cell(row.get(key)) for key in fields})
        aggregates={}
        for row in observations:
            variant=row.get("variant","unknown"); aggregates.setdefault(variant,[])
            if isinstance(row.get("correct"),bool): aggregates[variant].append(int(row["correct"]))
        table=output_dir/"publication_table.csv"
        with table.open("w",newline="",encoding="utf-8") as handle:
            writer=csv.writer(handle); writer.writerow(("variant","n","accuracy"))
            for variant,values in sorted(aggregates.items()):
                writer.writerow((variant,len(values),sum(values)/len(values) if values else "NOT_EVALUABLE"))
        (output_dir/"statistics.json").write_text(json.dumps(statistics,indent=2,sort_keys=True),encoding="utf-8")
        self._svg(output_dir/"accuracy.svg",aggregates)
        artefacts=[path for path in output_dir.iterdir() if path.is_file() and path.name!="manifest.json"]
        manifest={**metadata,"artefacts":{path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                                           for path in sorted(artefacts)}}
        (output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8")
        return manifest

    @staticmethod
    def _svg(path,aggregates):
        rows=[]
        for index,(name,values) in enumerate(sorted(aggregates.items())):
            score=sum(values)/len(values) if values else 0; width=int(score*400); y=25+index*28
            rows.append(f'<text x="5" y="{y}">{name}</text><rect x="150" y="{y-15}" width="{width}" height="18" fill="#3568a8"/><text x="{155+width}" y="{y}">{score:.3f}</text>')
        height=max(60,40+len(rows)*28)
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="650" height="{height}">{"".join(rows)}</svg>',encoding="utf-8")


def _cell(value):
    return json.dumps(value,sort_keys=True) if isinstance(value,(dict,list,tuple)) else value
