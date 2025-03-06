# Copyright 2025 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for Genkit document."""

from genkit.ai.document import (
    Document,
    MediaPart,
    MediaPartModel,
    TextPart,
)
from genkit.ai.embedding import EmbeddingModel


def test_makes_deep_copy() -> None:
    content = [TextPart(text='some text')]
    metadata = {'foo': 'bar'}
    doc = Document(content=content, metadata=metadata)

    content[0].text = 'other text'
    metadata['foo'] = 'faz'

    assert doc.content[0].text == 'some text'
    assert doc.metadata['foo'] == 'bar'


def test_simple_text_document() -> None:
    doc = Document.from_text('sample text')

    assert doc.text() == 'sample text'


def test_media_document() -> None:
    doc = Document.from_media(url='data:one')

    assert doc.media() == [
        MediaPartModel(url='data:one'),
    ]


def test_from_data_text_document() -> None:
    data = 'foo'
    data_type = 'text'
    metadata = {'embedMetadata': {'embeddingType': 'text'}}
    doc = Document.from_data(data, data_type, metadata)

    assert doc.text() == data
    assert doc.metadata == metadata
    assert doc.data_type() == data_type


def test_from_data_media_document() -> None:
    data = 'iVBORw0KGgoAAAANSUhEUgAAAAjCB0C8AAAAASUVORK5CYII='
    data_type = 'image/png'
    metadata = {'embedMetadata': {'embeddingType': 'image'}}
    doc = Document.from_data(data, data_type, metadata)

    assert doc.media() == [
        MediaPartModel(url=data, content_type=data_type),
    ]
    assert doc.metadata == metadata
    assert doc.data_type() == data_type


def test_concatenates_text() -> None:
    content = [TextPart(text='hello'), TextPart(text='world')]
    doc = Document(content=content)

    assert doc.text() == 'helloworld'


def test_multiple_media_document() -> None:
    content = [
        MediaPart(media=MediaPartModel(url='data:one')),
        MediaPart(media=MediaPartModel(url='data:two')),
    ]
    doc = Document(content=content)

    assert doc.media() == [
        MediaPartModel(url='data:one'),
        MediaPartModel(url='data:two'),
    ]


def test_data_with_text() -> None:
    doc = Document.from_text('hello')

    assert doc.data() == 'hello'


def test_data_with_media() -> None:
    doc = Document.from_media(
        url='gs://somebucket/someimage.png', content_type='image/png'
    )

    assert doc.data() == 'gs://somebucket/someimage.png'


def test_data_type_with_text() -> None:
    doc = Document.from_text('hello')

    assert doc.data_type() == 'text'


def test_data_type_with_media() -> None:
    doc = Document.from_media(
        url='gs://somebucket/someimage.png', content_type='image/png'
    )

    assert doc.data_type() == 'image/png'


def test_get_embedding_documents() -> None:
    doc = Document.from_text('foo')
    embeddings: list[EmbeddingModel] = [
        EmbeddingModel(embedding=[0.1, 0.2, 0.3])
    ]
    docs = doc.get_embedding_documents(embeddings)

    assert docs == [doc]


def test_get_embedding_documents_multiple_embeddings() -> None:
    url = 'gs://somebucket/somevideo.mp4'
    content_type = 'video/mp4'
    metadata = {'start': 0, 'end': 60}
    doc = Document.from_media(url, content_type, metadata)
    embeddings: list[EmbeddingModel] = []

    for start in range(0, 60, 15):
        embeddings.append(make_test_embedding(start))
    docs = doc.get_embedding_documents(embeddings)

    assert len(docs) == len(embeddings)

    for i in range(len(docs)):
        assert docs[i].content == doc.content
        assert docs[i].metadata['embedMetadata'] == embeddings[i].metadata
        orig_metadata = docs[i].metadata
        orig_metadata.pop('embedMetadata', None)
        assert orig_metadata, doc.metadata


def make_test_embedding(start: int) -> EmbeddingModel:
    return EmbeddingModel(
        embedding=[0.1, 0.2, 0.3],
        metadata={'embeddingType': 'video', 'start': start, 'end': start + 15},
    )
