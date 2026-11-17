import json
from pathlib import Path
import tempfile
import unittest
from lyrics_choices import choose,choices
from lyrics_download import fetch

class ChoicesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.audio=self.root/'Tagged singer - Fixture.wav';self.audio.touch()
        self.record={'id':123,'trackName':'Fixture','artistName':'Other singer','albumName':'Archive',
                     'duration':100,'syncedLyrics':'[00:01]Fixture line','plainLyrics':'Fixture text'}
    def tearDown(self):self.tmp.cleanup()
    def offer(self):
        def lookup(endpoint,query):
            return [self.record] if endpoint=='/search' and 'artist_name' not in query else None
        return fetch(self.audio,{'TITLE':'Fixture','ARTIST':'Tagged singer'},100,
                     allowed_root=self.root,permission=lambda:True,lookup=lookup)
    def pick(self,**kwargs):
        return choose(self.audio,123,allowed_root=self.root,permission=kwargs.pop('permission',lambda:True),
                      lookup=kwargs.pop('lookup',lambda *args:self.record),**kwargs)
    def test_cross_artist_only_offered_not_applied(self):
        self.assertIn('Choose',self.offer());self.assertFalse(self.audio.with_suffix('.lrc').exists())
        self.assertEqual(choices(self.audio)[0]['artistName'],'Other singer')
    def test_explicit_selection_saves_remembered_local_file(self):
        self.offer();self.assertIn('saved',self.pick());self.assertTrue(self.audio.with_suffix('.lrc').exists())
        self.assertEqual(choices(self.audio),[])
        report=json.loads(self.audio.with_suffix('.lyrics-source.json').read_text())
        self.assertIn('Explicit user choice',report['selection_method']);self.assertFalse(report['auditory_sync_accepted'])
    def test_text_only_never_fakes_lrc(self):
        self.record['syncedLyrics']=None;self.offer()
        self.assertIn('No timing',self.pick());self.assertFalse(self.audio.with_suffix('.lrc').exists())
        self.assertTrue(self.audio.with_suffix('.txt').exists())
    def test_disabled_and_invalid_selection(self):
        self.offer();self.assertEqual(self.pick(permission=lambda:False),'Auto Lyrics off')
        self.assertFalse(self.audio.with_suffix('.lrc').exists())
        self.record['duration']=130
        self.assertIn('mismatch',self.pick())
    def test_existing_lrc_preserved(self):
        self.offer();p=self.audio.with_suffix('.lrc');p.write_text('User file')
        self.pick();self.assertEqual(p.read_text(),'User file')

if __name__=='__main__':unittest.main()
