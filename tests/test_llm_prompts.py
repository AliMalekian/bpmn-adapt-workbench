import unittest


class LlmAndPromptTests(unittest.TestCase):
    def test_mock_llm_is_deterministic_and_schema_aware(self):
        from bpmn_adapt.llm.mock import MockLLMClient

        client = MockLLMClient({"analyse": {"status": "APPROVE", "reason": "ok"}})
        first = client.complete("system", "user", schema_name="analyse")
        second = client.complete("different", "input", schema_name="analyse")
        self.assertEqual(first, second)
        self.assertEqual("APPROVE", first["status"])

    def test_hash_embeddings_are_deterministic_and_semantic_tokens_overlap(self):
        from bpmn_adapt.llm.embedding import HashEmbeddingClient, cosine_similarity

        client = HashEmbeddingClient(dimensions=64)
        same = cosine_similarity(client.embed("remove task"), client.embed("remove task"))
        related = cosine_similarity(client.embed("remove the task"), client.embed("remove activity"))
        unrelated = cosine_similarity(client.embed("remove task"), client.embed("weather forecast"))
        self.assertAlmostEqual(1.0, same)
        self.assertGreater(related, unrelated)

    def test_all_agent_prompts_are_versioned_and_have_boundaries(self):
        from bpmn_adapt.prompts.loader import load_prompt

        for agent in ("orchestrator", "analyst", "modeler", "experimenter"):
            prompt = load_prompt(agent, "v1")
            self.assertIn(f"prompt-id: {agent}_v1", prompt)
            self.assertIn("Output contract", prompt)
            self.assertIn("must not", prompt.lower())


if __name__ == "__main__":
    unittest.main()
