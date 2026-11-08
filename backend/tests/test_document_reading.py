import asyncio
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from fastapi import HTTPException,UploadFile
from evidence_io import extract_file
from read_document import image
from investigator import validate_sources

FIXTURES=Path(__file__).parent/'fixtures'/'ocr'


@pytest.mark.parametrize('name,mime',[('receipt.png','image/png'),('scanned-receipt.pdf','application/pdf'),('unreadable.png','image/png')])
def test_real_offline_ocr_on_authored_originals(name,mime):
    if not (os.getenv('TESSERACT_CMD') or shutil.which('tesseract')):pytest.skip('Install Tesseract to run real OCR; CI installs it')
    raw=(FIXTURES/name).read_bytes()
    p=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'read_document.py'),mime],input=raw,capture_output=True,timeout=50)
    assert p.returncode==0
    result=json.loads(p.stdout)
    if name=='unreadable.png':
        assert result['status']=='uncertain' and 'Unreadable' in result['text']
        assert '812.02' not in result['text']
    else:
        assert '812.02' in result['text'] and 'TEST-2048' in result['text']
        assert 'No goods were shipped' in result['text']
        # A long tracking string can be low-confidence even on a printed
        # receipt. Abstention is valid; never force the expected digits.
        assert 'TEST123456789' in result['text'] or '[unclear]' in result['text']
        assert result['pages'][0]['words']
        assert result['pages'][0]['method']=='tesseract'


def test_upload_preserves_original_and_defers_reading_to_durable_worker():
    raw=(FIXTURES/'receipt.png').read_bytes()
    result=asyncio.run(extract_file(UploadFile(filename='receipt.png',file=io.BytesIO(raw)),deferred=True))
    assert result[0]==raw and result[4]['status']=='pending'
    assert '812.02' not in result[1]


@pytest.mark.parametrize('raw,name',[(b'<svg onload="fetch(\'private\')"/>','evil.png'),(b'MZexecutable','label.jpg'),(b'%PDF-broken','scan.pdf')])
def test_active_invalid_or_mislabeled_uploads_rejected(raw,name):
    with pytest.raises(HTTPException) as e:
        asyncio.run(extract_file(UploadFile(filename=name,file=io.BytesIO(raw)),deferred=True))
    assert e.value.status_code==422


def test_transcription_quote_is_not_mislabeled_as_original_verified_text():
    quote='Total: USD 812.02'
    claim={'id':'C','source_id':'E','quote':quote,'field':'amount','value':'812.02'}
    result=validate_sources({'claims':[claim],'hypotheses':[],'requests':[]},[
        {'id':'E','text':'[Page 1]\n'+quote,'sha256':'a'*64,'extraction':{'status':'uncertain'}}])
    c=result['claims'][0]
    assert c['source_check']=='quote_in_machine_transcription'
    assert not c['origin_verified'] and c['extraction_status']=='uncertain'
    assert c['passage_start']==9


def test_vision_text_cannot_invent_automatic_research_urls():
    from automatic_investigation import references
    s={'id':'E','text':'https://invented.example/policy','extraction':{'pages':[{'offline_text':'No URL in original offline text'}]}}
    assert references([s])==[]
