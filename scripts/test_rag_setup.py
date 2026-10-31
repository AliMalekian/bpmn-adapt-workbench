from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication

s = Settings.load(overrides={'llm_mode': 'live'})
print('embedding_provider:', s.embedding_provider)
print('embedding_model:', s.embedding_model)
try:
    import sentence_transformers
    print('sentence_transformers version:', sentence_transformers.__version__)
except Exception as e:
    print('sentence_transformers not installed:', e)
try:
    app = RuntimeAdaptationApplication.from_settings(s)
    print('app.rag:', type(app.rag))
    print('app.rag.embedding_client:', type(app.rag.embedding_client))
    print('app.rag.retriever:', type(app.rag.retriever))
    print('app.rag.vector_store:', type(app.rag.vector_store))
except Exception as e:
    import traceback
    print('Error creating app:', type(e), e)
    traceback.print_exc()
