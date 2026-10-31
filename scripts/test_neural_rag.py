import time
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication

s = Settings.load(overrides={'llm_mode': 'live', 'embedding_provider': 'sentence_transformers'})
print('embedding_provider:', s.embedding_provider)
print('embedding_model:', s.embedding_model)
t0 = time.time()
app = RuntimeAdaptationApplication.from_settings(s)
print(f'App initialized in {time.time() - t0:.2f}s')
print('app.rag:', type(app.rag))
print('app.rag.embedding_client:', type(app.rag.embedding_client))
print('app.rag.retriever:', type(app.rag.retriever))
print('app.rag.vector_store:', type(app.rag.vector_store))

# Test encode query
q_emb = app.rag.embedding_client.encode_queries(["Remove package goods task"])
print("Query embedding shape:", q_emb.shape)
