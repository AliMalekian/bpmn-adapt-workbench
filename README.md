# BPMN Adapt Workbench

A runtime BPMN adaptation workbench using a 4-agent pipeline with live LLM calls, RAG, and simulation-based verification.

## Quick Start

1. Install dependencies:
```bash
pip install -e .
```

2. Configure at least one provider (see [docs/USER_MANUAL.md](docs/USER_MANUAL.md)).

3. Launch the GUI:
```bash
bpmn-adapt gui
```

## Features

- 4-agent pipeline: Orchestrator, Analyst, Modeler, Experimenter
- Multi-provider support: Groq, Google AI Studio, UM LLM (Ferdowsi University), OpenRouter, OpenAI GPT, and custom providers.
- Runtime provider management (add/change API keys without restart).
- Automated benchmark across 82 datasets and 4 operation types.
- Real screenshot capture with metadata banners.
- Multi-provider comparison with McNemar and Wilcoxon tests.
- Checkpoint/resume for long-running benchmarks.
- Live log visualization in the GUI.

## Documentation

- [User Manual](docs/USER_MANUAL.md)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Design Specification](docs/superpowers/specs/2026-09-22-wavelet-progressive-pgsr-design.md)

## License

See LICENSE.
