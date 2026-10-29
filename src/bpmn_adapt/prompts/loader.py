"""Load editable, versioned prompt package resources."""
from importlib.resources import files


def load_prompt(agent: str, version: str = "v2") -> str:
    allowed = {"orchestrator", "analyst", "modeler", "experimenter"}
    if agent not in allowed or version not in {"v1", "v2"}:
        raise ValueError(f"Unsupported prompt: {agent}_{version}")
    return files("bpmn_adapt.prompts").joinpath(f"{agent}_{version}.md").read_text(encoding="utf-8")

