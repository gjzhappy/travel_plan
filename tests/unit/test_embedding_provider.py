from travel_plan.retrieval.embedding_provider import BGEEmbeddingProvider


class ModelStub:
    def eval(self):
        return self

    def get_sentence_embedding_dimension(self):
        return 2

    def encode(self, texts, **kwargs):
        import numpy

        return numpy.asarray([[0.6, 0.8] for _ in texts], dtype="float32")


def test_bge_provider_is_consistent_and_reports_dimension():
    provider = object.__new__(BGEEmbeddingProvider)
    provider.model = ModelStub()
    first = provider.embed("带孩子，科技，轻松")
    assert first == provider.embed("带孩子，科技，轻松")
    assert provider.embed_batch(["博物馆", "夜景"]) == [[0.6000000238418579, 0.800000011920929], [0.6000000238418579, 0.800000011920929]]
    assert provider.dimension == 2
