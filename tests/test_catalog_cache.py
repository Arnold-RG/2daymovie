import json
from services import library


def test_catalog_cache_refreshes_and_isolates_callers(tmp_path, monkeypatch):
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps([{'id': 1, 'title': 'First', 'trailer_key': 'abcdefghijk'}]))
    monkeypatch.setattr(library, 'CATALOG_PATH', path)
    library._read_catalog.cache_clear()
    first = library.get_catalog_movie(1)
    first['title'] = 'Mutated'
    assert library.get_catalog_movie(1)['title'] == 'First'
    assert library._read_catalog.cache_info().hits == 1
    path.write_text(json.dumps([{'id': 2, 'title': 'A changed catalog', 'trailer_key': 'abcdefghijk'}]))
    assert library._load_resolved()[0]['id'] == 2
    path.unlink()
    assert library._load_resolved() == []
