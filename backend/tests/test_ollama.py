import asyncio

from app.services import ollama


class FakeResponse:
    def __init__(self, count: int) -> None:
        self.count = count

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, list[list[float]]]:
        return {"embeddings": [[float(index)] for index in range(self.count)]}


class FakeClient:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, _url: str, json: dict[str, object]) -> FakeResponse:
        inputs = json["input"]
        assert isinstance(inputs, list)
        self.batch_sizes.append(len(inputs))
        return FakeResponse(len(inputs))


def test_embeddings_are_generated_in_bounded_batches(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **_: client)

    embeddings = asyncio.run(
        ollama.create_embeddings([f"chunk-{index}" for index in range(65)])
    )

    assert client.batch_sizes == [32, 32, 1]
    assert len(embeddings) == 65
