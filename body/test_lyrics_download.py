import json
from pathlib import Path
import tempfile
import unittest
from lyrics_download import fetch,matching,identity,select_candidate

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.audio=self.root/'Artist - Title.wav';self.audio.touch()
        self.record={'id':123,'trackName':'Title','artistName':'Artist','albumName':'Album','duration':100,
                     'syncedLyrics':'[00:01]Fixture first\n[00:05]Fixture next','plainLyrics':'Fixture first','instrumental':False}
        self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def run_fetch(self,record=None,**kwargs):
        def lookup(endpoint,query):
            self.calls.append(endpoint)
            return (record if record is not None else self.record) if endpoint=='/get' else []
        return fetch(self.audio,{'TITLE':'Title','ARTIST':'Artist','ALBUM':'Album'},100,
                     allowed_root=self.root,permission=kwargs.pop('permission',lambda:True),lookup=kwargs.pop('lookup',lookup),**kwargs)
    def test_download_sidecar_and_provenance(self):
        self.assertIn('downloaded',self.run_fetch())
        self.assertTrue(self.audio.with_suffix('.lrc').exists())
        self.assertEqual(json.loads(self.audio.with_suffix('.lyrics-source.json').read_text())['record_id'],123)
    def test_existing_lrc_never_overwritten_or_queried(self):
        p=self.audio.with_suffix('.LRC');p.write_text('Existing')
        self.run_fetch();self.assertFalse(self.calls);self.assertEqual(p.read_text(),'Existing')
    def test_wrong_version_duration_and_negative_cache(self):
        record=dict(self.record,duration=105)
        self.assertIn('No confident match',self.run_fetch(record))
        self.assertFalse(self.audio.with_suffix('.lrc').exists())
        self.calls.clear();self.run_fetch(record);self.assertFalse(self.calls)
    def test_plain_only_no_fake_timestamps(self):
        record=dict(self.record,syncedLyrics=None)
        self.assertIn('No timing',self.run_fetch(record))
        self.assertFalse(self.audio.with_suffix('.lrc').exists())
        self.assertEqual(self.audio.with_suffix('.txt').read_text(),'Fixture first')
    def test_ambiguous_search_rejected(self):
        def lookup(endpoint,query):return None if endpoint=='/get' else [self.record,dict(self.record,id=124,syncedLyrics='[00:02]Different timing')]
        self.assertIn('Ambiguous versions',self.run_fetch(lookup=lookup))
    def test_artist_aliases_and_simplified_title(self):
        query={'track_name':'卡門','artist_name':'Grace Chang','album_name':'Compilation','duration':100}
        self.assertTrue(matching(dict(self.record,trackName='卡门',artistName='葛兰'),query))
        self.assertFalse(matching(dict(self.record,trackName='卡门',artistName='Other singer'),query))
    def test_album_is_preference_and_identical_reissues(self):
        query={'track_name':'Title','artist_name':'Artist','album_name':'Album','duration':100}
        record,_=select_candidate([dict(self.record,albumName='Different compilation')],query)
        self.assertIsNotNone(record)
        record,_=select_candidate([self.record,dict(self.record,id=124,albumName='Other')],query)
        self.assertEqual(record['id'],123)
        query['album_name']='Unknown'
        record,_=select_candidate([self.record,dict(self.record,id=124,albumName='Other',syncedLyrics=self.record['syncedLyrics']+'\n[by:Fixture]')],query)
        self.assertIsNotNone(record)  # Equal parsed timing/text despite reissue metadata.
    def test_soundtrack_credit_and_artist_scoped_title_alias(self):
        query={'track_name':'花樣年華','artist_name':'周璇','album_name':'Compilation','duration':186.826667}
        record=dict(self.record,trackName='花樣的年華 - 電影[花樣年華]配樂',artistName='周璇',duration=188)
        self.assertTrue(matching(record,query))
        record['trackName']='花樣的年華 (電影[花樣年華]配樂)'
        self.assertTrue(matching(record,query))
        record['trackName']='花樣的年華 (Live)'
        self.assertFalse(matching(record,query))
        record.update(trackName='花樣的年華',artistName='Other singer')
        self.assertFalse(matching(record,query))
    def test_version_qualifier_and_old_cache(self):
        query={'track_name':'Title (Live)','artist_name':'Artist','album_name':'','duration':100}
        self.assertFalse(matching(self.record,query))
        self.audio.with_suffix('.lyrics-source.json').write_text(json.dumps({'query':identity(self.audio,{'TITLE':'Title','ARTIST':'Artist','ALBUM':'Album'},100),'retry_after':9999999999,'status':'old failure'}))
        self.assertIn('downloaded',self.run_fetch())
    def test_disabled_no_network_and_no_files(self):
        self.assertEqual(self.run_fetch(permission=lambda:False),'Auto Lyrics off')
        self.assertFalse(self.calls);self.assertFalse(self.audio.with_suffix('.lyrics-source.json').exists())
    def test_network_failure_and_missing_identity(self):
        def fail(*args):raise OSError('offline')
        self.assertEqual(self.run_fetch(lookup=fail),'Lyrics lookup failed')
        self.assertIsNone(identity(Path('Just title.mp3'),{},100))
    def test_permission_revoked_before_write(self):
        allowed=[True]
        def lookup(endpoint,query):allowed[0]=False;return self.record
        self.assertEqual(self.run_fetch(permission=lambda:allowed[0],lookup=lookup),'Auto Lyrics off')
        self.assertFalse(self.audio.with_suffix('.lrc').exists())

if __name__=='__main__':unittest.main()
