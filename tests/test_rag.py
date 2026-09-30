import json

import pytest

from sera.rag import Corpus, RagExample, RagIndex, make_tasks


def corpus(tmp_path):
    source = tmp_path / 'documents.jsonl'
    source.write_text('\n'.join(json.dumps(d) for d in [
        {'id': 'cedar', 'text': 'Cedar daily backup starts at 03:00 UTC. Retention is 14 days.'},
        {'id': 'birch', 'text': 'Birch daily backup starts at 06:00 UTC. Retention is 30 days.'}]))
    return source


def test_index_roundtrip_grounded_tasks_and_no_answer_leak(tmp_path):
    source = corpus(tmp_path)
    inventory = Corpus(source).inspect()
    assert inventory['document_count'] == 2
    index = RagIndex.build(source, tmp_path / 'index', chunk_words=128,
                           expected_hash=inventory['corpus_hash'])
    hits = index.search('Cedar backup time', top_k=1)
    assert hits[0]['document_id'] == 'cedar'
    example = RagExample(question='When does Cedar daily backup start?', answer='03:00 UTC',
                         document_id='cedar', evidence='starts at 03:00 UTC')
    tasks, retrieval = make_tasks(index, [example], top_k=1)
    assert tasks[0].expected_json == {'answer': '03:00 UTC', 'source': 'cedar'}
    assert '03:00 UTC' in tasks[0].prompt[1]['content']
    assert 'expected' not in tasks[0].prompt[1]['content']
    assert retrieval['evidence_recall'] == 1
    assert RagIndex(index.folder, expected_hash=index.manifest['index_hash']).search('Birch')[0]['document_id'] == 'birch'


def test_source_changes_duplicates_and_ungrounded_answers_fail(tmp_path):
    source = corpus(tmp_path)
    old = Corpus(source).inspect()['corpus_hash']
    source.write_text(source.read_text() + '\n' + json.dumps({'id': 'oak', 'text': 'Oak'}))
    with pytest.raises(ValueError, match='changed'):
        RagIndex.build(source, tmp_path / 'changed', chunk_words=128, expected_hash=old)
    index = RagIndex.build(source, tmp_path / 'valid', chunk_words=128)
    with pytest.raises(ValueError, match='evidence'):
        make_tasks(index, [RagExample(question='When?', answer='noon', document_id='cedar', evidence='noon')], top_k=1)
    with pytest.raises(ValueError, match='answer'):
        make_tasks(index, [RagExample(question='When?', answer='noon', document_id='cedar', evidence='03:00 UTC')], top_k=1)
    source.write_text(source.read_text() + '\n' + json.dumps({'id': 'cedar', 'text': 'Duplicate'}))
    with pytest.raises(ValueError, match='Duplicate'):
        RagIndex.build(source, tmp_path / 'duplicates', chunk_words=128)


def test_retrieval_misses_are_not_repaired_using_gold_answers(tmp_path):
    index = RagIndex.build(corpus(tmp_path), tmp_path / 'index', chunk_words=128)
    example = RagExample(question='Birch backup time', answer='03:00 UTC', document_id='cedar', evidence='03:00 UTC')
    tasks, metrics = make_tasks(index, [example], top_k=1)
    assert metrics['evidence_recall'] == 0
    assert 'Cedar' not in tasks[0].prompt[1]['content']
    assert tasks[0].expected_json['source'] == 'cedar'


def test_query_is_data_and_empty_query_does_not_scan_corpus(tmp_path):
    index = RagIndex.build(corpus(tmp_path), tmp_path / 'index', chunk_words=128)
    assert index.search('***') == []
    assert isinstance(index.search('" OR * ; DROP TABLE chunks; --'), list)
    assert index.search('Cedar')[0]['document_id'] == 'cedar'
    with pytest.raises(ValueError):
        index.search('hi', top_k=10000)


def test_index_integrity_and_directory_symlinks(tmp_path):
    folder = tmp_path / 'docs'
    folder.mkdir()
    (folder / 'one.txt').write_text('A useful document.')
    (folder / 'leak.txt').symlink_to(corpus(tmp_path))
    with pytest.raises(ValueError, match='symlink'):
        Corpus(folder).inspect()
    (folder / 'leak.txt').unlink()
    index = RagIndex.build(folder, tmp_path / 'index', chunk_words=128)
    with (index.folder / 'index.sqlite3').open('ab') as handle:
        handle.write(b'tamper')
    with pytest.raises(ValueError, match='integrity'):
        RagIndex(index.folder)


def test_unsupported_files_and_empty_corpora_fail(tmp_path):
    path = tmp_path / 'file.pdf'
    path.write_bytes(b'not a PDF')
    with pytest.raises(ValueError, match='JSONL'):
        Corpus(path).inspect()
    path = tmp_path / 'empty.jsonl'
    path.write_text('')
    with pytest.raises(ValueError, match='empty'):
        Corpus(path).inspect()


def test_pipeline_cites_retrieved_text_and_abstains_on_unsupported_output(tmp_path):
    from sera.rag import RagPipeline
    class Model:
        text = '{"answer":"03:00 UTC","source":"cedar"}'
        closed = False
        def generate(self, *args, **kwargs):
            return {'text': self.text}
        def close(self):
            self.closed = True
    model = Model()
    index = RagIndex.build(corpus(tmp_path), tmp_path / 'index', chunk_words=128)
    with RagPipeline(model, index, top_k=1, max_tokens=64, seed=0) as pipeline:
        assert pipeline.answer('Cedar backup')['supported']
        model.text = '{"answer":"noon","source":"cedar"}'
        assert pipeline.answer('Cedar backup')['answer'] is None
        model.text = '{"answer":"03:00 UTC","source":"invented"}'
        assert not pipeline.answer('Cedar backup')['supported']
        assert pipeline.answer('zzzzzzz')['reason'] == 'no-retrieval-match'
    assert model.closed


def test_directory_enumeration_obeys_document_limit(tmp_path, monkeypatch):
    monkeypatch.setattr('sera.rag.MAX_DOCUMENTS', 2)
    folder = tmp_path / 'docs'
    folder.mkdir()
    for i in range(3):
        (folder / f'{i}.txt').write_text('A document.')
    def oversized_tree(self, pattern):
        yield from [folder / f'{i}.txt' for i in range(3)]
        raise RuntimeError('The rest of this oversized tree must not be enumerated')
    monkeypatch.setattr(type(folder), 'rglob', oversized_tree)
    with pytest.raises(ValueError, match='limits'):
        list(Corpus(folder).documents())


def test_answer_variants_are_explicit_grounded_and_not_in_prompt(tmp_path):
    index = RagIndex.build(corpus(tmp_path), tmp_path / 'index', chunk_words=128)
    value = {'question': 'How many days does Cedar retain backups?', 'answer': '14 days',
             'document_id': 'cedar', 'evidence': 'Retention is 14 days.', 'accepted_answers': ['14']}
    tasks, _ = make_tasks(index, [value], top_k=1)
    assert tasks[0].accepted_json == [{'answer': '14', 'source': 'cedar'}]
    assert 'accepted_answers' not in tasks[0].prompt[1]['content']
    with pytest.raises(ValueError, match='answer'):
        make_tasks(index, [value | {'accepted_answers': ['30']}], top_k=1)


def test_answer_support_rejects_partial_numbers_and_words(tmp_path):
    index = RagIndex.build(corpus(tmp_path), tmp_path / 'index', chunk_words=128)
    value = {'question': 'How many days are backups retained?', 'answer': '14 days',
             'document_id': 'cedar', 'evidence': 'Retention is 14 days.', 'accepted_answers': ['4']}
    with pytest.raises(ValueError, match='answer'):
        make_tasks(index, [value], top_k=1)
