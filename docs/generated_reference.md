# Generated CLI and configuration reference

This file is generated from the executable parser and `.env.example`. Regenerate it with `python scripts/generate_reference.py`.

## Global CLI help

```text
usage: bpmn-adapt [-h] [--config CONFIG] [--json] [--seed SEED]
                  [--run-id RUN_ID] [--offline | --live]
                  {gui,ingest,index-rag,validate,simulate,evaluate,report,baseline,deploy,analyse,plan,adapt,revoke-rag,migrate,approve,reject,inspect,batch,export,replay}
                  ...

positional arguments:
  {gui,ingest,index-rag,validate,simulate,evaluate,report,baseline,deploy,analyse,plan,adapt,revoke-rag,migrate,approve,reject,inspect,batch,export,replay}

options:
  -h, --help            show this help message and exit
  --config CONFIG
  --json
  --seed SEED
  --run-id RUN_ID
  --offline
  --live
```

## `adapt`

```text
usage: bpmn-adapt adapt [-h] [--target TARGET] [--state STATE]
                        [--operation {ADD,MODIFY,REMOVE,RE_ADD}]
                        folder request

positional arguments:
  folder
  request

options:
  -h, --help            show this help message and exit
  --target TARGET
  --state STATE
  --operation {ADD,MODIFY,REMOVE,RE_ADD}
```

## `analyse`

```text
usage: bpmn-adapt analyse [-h] [--target TARGET] [--state STATE]
                          [--operation {ADD,MODIFY,REMOVE,RE_ADD}]
                          folder request

positional arguments:
  folder
  request

options:
  -h, --help            show this help message and exit
  --target TARGET
  --state STATE
  --operation {ADD,MODIFY,REMOVE,RE_ADD}
```

## `approve`

```text
usage: bpmn-adapt approve [-h] [--actor ACTOR] approval_run_id reason

positional arguments:
  approval_run_id
  reason

options:
  -h, --help       show this help message and exit
  --actor ACTOR
```

## `baseline`

```text
usage: bpmn-adapt baseline [-h] [--variant VARIANT] folder

positional arguments:
  folder

options:
  -h, --help         show this help message and exit
  --variant VARIANT
```

## `batch`

```text
usage: bpmn-adapt batch [-h] [--request REQUEST] folders [folders ...]

positional arguments:
  folders

options:
  -h, --help         show this help message and exit
  --request REQUEST
```

## `deploy`

```text
usage: bpmn-adapt deploy [-h] [--create-instance] [--variables VARIABLES]
                         folder

positional arguments:
  folder

options:
  -h, --help            show this help message and exit
  --create-instance
  --variables VARIABLES
```

## `evaluate`

```text
usage: bpmn-adapt evaluate [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## `export`

```text
usage: bpmn-adapt export [-h] export_run_id destination

positional arguments:
  export_run_id
  destination

options:
  -h, --help     show this help message and exit
```

## `gui`

```text
usage: bpmn-adapt gui [-h]

options:
  -h, --help  show this help message and exit
```

## `index-rag`

```text
usage: bpmn-adapt index-rag [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## `ingest`

```text
usage: bpmn-adapt ingest [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## `inspect`

```text
usage: bpmn-adapt inspect [-h] [--instance INSTANCE] [folder]

positional arguments:
  folder

options:
  -h, --help           show this help message and exit
  --instance INSTANCE
```

## `migrate`

```text
usage: bpmn-adapt migrate [-h] [--mapping MAPPING]
                          instance_id target_definition_key

positional arguments:
  instance_id
  target_definition_key

options:
  -h, --help            show this help message and exit
  --mapping MAPPING
```

## `plan`

```text
usage: bpmn-adapt plan [-h] [--target TARGET] [--state STATE] folder request

positional arguments:
  folder
  request

options:
  -h, --help       show this help message and exit
  --target TARGET
  --state STATE
```

## `reject`

```text
usage: bpmn-adapt reject [-h] [--actor ACTOR] approval_run_id reason

positional arguments:
  approval_run_id
  reason

options:
  -h, --help       show this help message and exit
  --actor ACTOR
```

## `replay`

```text
usage: bpmn-adapt replay [-h] replay_run_id

positional arguments:
  replay_run_id

options:
  -h, --help     show this help message and exit
```

## `report`

```text
usage: bpmn-adapt report [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## `revoke-rag`

```text
usage: bpmn-adapt revoke-rag [-h] evidence_id reason

positional arguments:
  evidence_id
  reason

options:
  -h, --help   show this help message and exit
```

## `simulate`

```text
usage: bpmn-adapt simulate [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## `validate`

```text
usage: bpmn-adapt validate [-h] folder

positional arguments:
  folder

options:
  -h, --help  show this help message and exit
```

## Environment variables

| Variable | Example/default |
|---|---|
| `ADAPT_LLM_MODE` | `mock` |
| `ADAPT_LLM_PROVIDER` | `openai_compatible` |
| `ADAPT_LLM_MODEL` | `example-model` |
| `ADAPT_LLM_BASE_URL` | `https://api.openai.com/v1` |
| `ADAPT_LLM_API_KEY` | *(empty)* |
| `ADAPT_LLM_TIMEOUT_SECONDS` | `60` |
| `ADAPT_LLM_MAX_RETRIES` | `2` |
| `ADAPT_LLM_RETRY_BACKOFF_SECONDS` | `1.0` |
| `ADAPT_LLM_RATE_LIMIT_REQUESTS_PER_MINUTE` | `30` |
| `ADAPT_EMBEDDING_PROVIDER` | `sentence_transformers` |
| `ADAPT_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `ADAPT_EMBEDDING_REVISION` | `main` |
| `ADAPT_EMBEDDING_DEVICE` | `cpu` |
| `ADAPT_EMBEDDING_BATCH_SIZE` | `32` |
| `ADAPT_VECTOR_BACKEND` | `local` |
| `ADAPT_VECTOR_PATH` | `experiments/vector_index` |
| `ADAPT_DATABASE_URL` | `sqlite:///experiments/runtime_bpmn.db` |
| `ADAPT_RAG_MODE` | `hybrid` |
| `ADAPT_RAG_SEMANTIC_WEIGHT` | `0.65` |
| `ADAPT_RAG_SYNTACTIC_WEIGHT` | `0.35` |
| `ADAPT_OUTPUT_ROOT` | `experiments/runs` |
| `ADAPT_MAX_AGENT_RETRIES` | `2` |
| `ADAPT_PLANNER_WEIGHT_TIME` | `0.4` |
| `ADAPT_PLANNER_WEIGHT_BUDGET` | `0.3` |
| `ADAPT_PLANNER_WEIGHT_RISK` | `0.3` |
| `ADAPT_PLANNER_MAX_STATES` | `10000` |
| `ADAPT_PLANNER_MAX_DEPTH` | `100` |
| `ADAPT_PLANNER_TIMEOUT_SECONDS` | `30` |
| `ADAPT_ENGINE_MODE` | `disabled` |
| `ADAPT_ENGINE_BASE_URL` | `http://localhost:8080` |
| `ADAPT_ENGINE_OAUTH_URL` | *(empty)* |
| `ADAPT_ENGINE_CLIENT_ID` | *(empty)* |
| `ADAPT_ENGINE_CLIENT_SECRET` | *(empty)* |
| `ADAPT_ENGINE_TENANT_ID` | `research` |
| `ADAPT_ENGINE_TIMEOUT_SECONDS` | `30` |
| `ADAPT_ENGINE_MAX_RETRIES` | `2` |
| `ADAPT_FORMAL_MODE` | `disabled` |
| `ADAPT_EXTERNAL_CHECKER_COMMAND` | *(empty)* |
| `ADAPT_EXTERNAL_CHECKER_TIMEOUT_SECONDS` | `30` |
| `ADAPT_EVALUATION_SEED` | `20260922` |
| `ADAPT_EVALUATION_REPETITIONS` | `5` |
