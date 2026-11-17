import tempfile
import unittest
from pathlib import Path
from lyrics import Lyrics,parse_lrc

class LyricsTests(unittest.TestCase):
    def test_timestamps_multiple_tags_and_sort(self):
        self.assertEqual(parse_lrc('[ar:Example]\n[01:02.3][00:02.03]Again\n[00:01]First'),
                         [(1,'First'),(2.03,'Again'),(62.3,'Again')])
    def test_offset_translations_and_word_timing(self):
        self.assertEqual(parse_lrc('[offset:+500]\n[00:01.000]<00:01.00>Hello\n[00:01]Translation'),
                         [(.5,'Hello\nTranslation')])
    def test_empty_line_and_invalid_timestamp(self):
        self.assertEqual(parse_lrc('[00:60]Invalid\n[00:01]Text\n[00:02]'),[(1,'Text'),(2,'')])
    def test_seek_pause_song_change_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            song=Path(directory)/'Song.wav';song.touch()
            song.with_suffix('.LRC').write_text('[00:01]One\n[00:03]Three',encoding='utf-8-sig')
            engine=Lyrics()
            self.assertEqual(engine.update(str(song),0),('Lyrics','','One'))
            self.assertEqual(engine.update(str(song),3.1),('Lyrics','Three',''))
            self.assertEqual(engine.update(str(song),3.1),('Lyrics','Three',''))
            self.assertEqual(engine.update(str(song),1.5),('Lyrics','One','Three'))
            self.assertEqual(engine.update(str(Path(directory)/'Other.wav'),2),('Lyrics unavailable','',''))
            self.assertEqual(engine.update(None,None),('Lyrics · No music playing','',''))
    def test_utf16_edit_and_file_url(self):
        with tempfile.TemporaryDirectory() as directory:
            song=Path(directory)/'Song with spaces.wav';song.touch()
            lrc=song.with_suffix('.lrc');lrc.write_text('[00:00]測試',encoding='utf-16')
            engine=Lyrics();self.assertEqual(engine.update(song.as_uri(),0)[1],'測試')
            lrc.write_text('[00:00]Updated fixture line',encoding='utf-8')
            self.assertEqual(engine.update(str(song),0)[1],'Updated fixture line')
    def test_remote_and_metadata_only(self):
        self.assertEqual(Lyrics().update('https://example.invalid/music',0)[0],'Lyrics · No music playing')
        self.assertEqual(parse_lrc('[ti:Title]\nUnsynchronized text'),[])

if __name__=='__main__':unittest.main()
