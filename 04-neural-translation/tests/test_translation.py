import importlib
import os
import tempfile
from pathlib import Path

os.environ.pop('NMT_RESEARCH_MODE',None)
os.environ.pop('NMT_MODEL_DIR',None)
os.environ['TRANSLATION_DB']=str(Path(tempfile.mkdtemp())/'nmt_tests.sqlite3')
from fastapi.testclient import TestClient
from server import app as mod
client=TestClient(mod.app)

def test_health_declares_no_model():
    d=client.get('/api/health').json()
    assert d['service']=='ok' and not d['model']['ready']
    assert d['text_retention'].startswith('metadata_only')

def test_languages_contain_four_and_all_pairs():
    d=client.get('/api/languages').json()
    assert {x['code'] for x in d['languages']}=={'en','hi','te','ko'}
    assert d['supported_pairs']==12

def test_unavailable_model_cannot_fake_translation():
    r=client.post('/api/translate',json={'text':'Good morning','source':'en','target':'te'})
    assert r.status_code==503
    assert 'does not fabricate' in r.json()['detail']

def test_validation_rejects_identical_languages_and_blank_text():
    assert client.post('/api/translate',json={'text':'Hello','source':'en','target':'en'}).status_code==422
    assert client.post('/api/translate',json={'text':'   ','source':'en','target':'ko'}).status_code==422

def test_private_metrics_start_empty():
    d=client.get('/api/metrics').json()
    assert d['total_completed_translations_and_evaluations']==0
    assert d['content_retained'] is False

def test_evaluation_needs_real_model():
    r=client.post('/api/evaluate',json={'text':'hello','source':'en','target':'hi','reference_translation':'नमस्ते'})
    assert r.status_code==503

def test_invalid_model_directory_does_not_claim_readiness(tmp_path,monkeypatch):
    monkeypatch.setenv('NMT_RESEARCH_MODE','1')
    monkeypatch.setenv('NMT_MODEL_DIR',str(tmp_path))
    assert mod.model_config()['ready'] is False
    assert client.post('/api/translate',json={'text':'hello','source':'en','target':'hi'}).status_code==503
