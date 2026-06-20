from app.services.documents import chunk_text, extract_text, hash_chunks


def test_extracts_utf8_text_file() -> None:
    assert extract_text("notes.txt", b"hello world") == "hello world"


def test_rejects_unsupported_file_type() -> None:
    try:
        extract_text("notes.csv", b"hello,world")
    except ValueError as error:
        assert "Supported file types" in str(error)
    else:
        raise AssertionError("Unsupported files must be rejected")


def test_chunk_text_preserves_overlap() -> None:
    text = " ".join(f"word-{index}" for index in range(12))
    chunks = chunk_text(text, chunk_size=5, overlap=2)

    assert len(chunks) == 4
    assert chunks[0].split()[-2:] == chunks[1].split()[:2]


def test_chunk_text_handles_empty_content() -> None:
    assert chunk_text("   ") == []


def test_hash_chunks_is_stable_and_content_sensitive() -> None:
    assert hash_chunks(["same content"]) == hash_chunks(["same content"])
    assert hash_chunks(["same content"]) != hash_chunks(["different content"])
