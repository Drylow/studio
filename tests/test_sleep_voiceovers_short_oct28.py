"""Offline paid-request, duration, and delivery preservation checks."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
import sleep_voiceovers_short_oct28 as batch


class ShortVoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.old=(batch.engine.STATE,batch.engine.SOURCE,batch.engine.OUT,batch.FRENCH_LEDGER)
        batch.engine.STATE=self.root/'state';batch.engine.STATE.mkdir()
        batch.engine.SOURCE=self.root/'sources';batch.engine.OUT=self.root/'out'
        batch.FRENCH_LEDGER=self.root/'french.json'
        batch.FRENCH_LEDGER.write_text(json.dumps({'generate_srt':True,'episodes':[{'parts':[{'state':'ready','characters':10000}]}]}))
        self.eid='DV-08-bene-gesserit';self.text=('A paragraph with a full ending.\n\n'*3200)
        source=batch.engine.SOURCE/self.eid;source.mkdir(parents=True)
        (source/'SCRIPT.txt').write_text(self.text,encoding='utf-8',newline='\n')
        folder=batch.engine.OUT/'Deep Void Theories'/self.eid;folder.mkdir(parents=True)
        (folder/'VOICEOVER.mp3').write_bytes(b'original-long-audio')
        (folder/'SCRIPT.txt').write_bytes(b'original-long-script')
        self.e={'id':self.eid,'state':'ready','script':self.eid+'/SCRIPT.txt','sha256':batch.text_digest(self.text),
                'characters':len(self.text),'words':len(self.text.split()),'title':'Example title',
                'delivery_folder':'Deep Void Theories/'+self.eid,'audio_file':'Deep Void Theories/'+self.eid+'/VOICEOVER.mp3',
                'previous_delivery_hashes':{n:batch.digest(folder/n) for n in ('VOICEOVER.mp3','SCRIPT.txt')},
                'parts':batch.partition(self.eid,self.text)}
        self.data={'episodes':[self.e]}

    def tearDown(self):
        batch.engine.STATE,batch.engine.SOURCE,batch.engine.OUT,batch.FRENCH_LEDGER=self.old
        self.temp.cleanup()

    def test_exact_partition_and_paid_prefix(self):
        for eid in (self.eid,'FR-04-daedric-princes'):
            parts=batch.partition(eid,self.text)
            self.assertEqual(''.join(self.text[p['start']:p['end']] for p in parts),self.text)
            self.assertTrue(all(10000<=p['characters']<=25000 for p in parts))
            if eid.startswith('FR'):
                self.assertEqual([(p['start'],p['end']) for p in parts[:2]],[(0,20584),(20584,41534)])

    def test_budget_preserves_french_reserve(self):
        c={'tts_characters':{'remaining':len(self.text)+11999}}
        with patch.object(batch.engine.tts,'algrow_credits',return_value=c),patch.object(batch.engine.tts,'_algrow_call') as api:
            self.assertFalse(batch.submit_pair(self.data));api.assert_not_called()

    def test_unknown_paid_request_never_retries(self):
        with patch.object(batch.engine.tts,'algrow_credits',return_value={'tts_characters':{'remaining':2000000}}),patch.object(batch.engine.tts,'_algrow_call',side_effect=TimeoutError('simulated')) as api:
            self.assertFalse(batch.submit_pair(self.data))
            self.assertEqual(self.e['parts'][0]['state'],'submission_unknown')
            with self.assertRaises(RuntimeError):batch.submit_pair(self.data)
            self.assertEqual(api.call_count,1)

    def test_pause_blocks_all_paid_work(self):
        (batch.engine.STATE/'pause-submissions.json').write_text('{}')
        with patch.object(batch.engine.tts,'_algrow_call') as api:
            self.assertFalse(batch.run(self.data));self.assertFalse(batch.submit_pair(self.data));api.assert_not_called()

    def test_delivery_has_strict_minimum_and_maximum(self):
        for seconds in (7199.99,9000.01):
            self.e['duration_seconds']=seconds
            with self.assertRaises(RuntimeError):batch.deliver(self.data,self.e,self.root/'new.mp3')
        self.assertEqual((batch.engine.OUT/self.e['audio_file']).read_bytes(),b'original-long-audio')

    def test_delivery_preserves_original_hardlink_and_replaces_script(self):
        new=self.root/'new.mp3';new.write_bytes(b'new-short-audio')
        self.e.update(duration_seconds=8400,audio_sha256=batch.digest(new),audio_bytes=new.stat().st_size)
        batch.deliver(self.data,self.e,new)
        folder=batch.engine.OUT/self.e['delivery_folder']
        self.assertEqual((folder/'VOICEOVER.mp3').read_bytes(),b'new-short-audio')
        self.assertEqual((folder/'SCRIPT.txt').read_text(),self.text)
        archive=batch.engine.OUT/'_Archives des anciens dossiers/Versions longues avant correction - 28 octobre 2026'/self.e['delivery_folder']
        self.assertEqual((archive/'VOICEOVER.mp3').read_bytes(),b'original-long-audio')
        self.assertEqual((archive/'SCRIPT.txt').read_bytes(),b'original-long-script')
        batch.deliver(self.data,self.e,new)
        self.assertEqual(self.e['state'],'verified')

    def test_external_change_prevents_delivery(self):
        new=self.root/'new.mp3';new.write_bytes(b'new-short-audio')
        self.e.update(duration_seconds=8400,audio_sha256=batch.digest(new),audio_bytes=new.stat().st_size)
        dest=batch.engine.OUT/self.e['audio_file'];dest.write_bytes(b'user-edited')
        batch.deliver(self.data,self.e,new)
        self.assertEqual(self.e['state'],'delivery_conflict');self.assertEqual(dest.read_bytes(),b'user-edited')

    def test_missing_qa_never_passes(self):
        part=self.e['parts'][0]
        with patch.object(batch.engine,'verify',side_effect=lambda p:p.update(state='verified')):
            batch.verify_part(part,'text')
        self.assertEqual(part['state'],'audio_review_required')

    def test_monitor_does_not_submit_ready_parts(self):
        with patch.object(batch.engine.tts,'_algrow_call') as api:
            batch.monitor(self.data);api.assert_not_called()


if __name__=='__main__':unittest.main()
