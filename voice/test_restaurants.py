import unittest
from unittest.mock import patch
import restaurants


class LookupTests(unittest.TestCase):
    def test_routing(self):
        self.assertTrue(restaurants.is_request('附近有什麼好吃的餐廳'))
        self.assertTrue(restaurants.is_request('find restaurants'))
        self.assertFalse(restaurants.is_request('播放夜來香'))

    def test_osm_parse(self):
        responses = [[{'lat':'34.0203253','lon':'-117.8659441'}],
                     {'elements':[{'type':'node','id':1,'lat':34.02,'lon':-117.86,
                                   'tags':{'name':'Test fixture only','cuisine':'chinese'}}]}]
        with patch.object(restaurants,'fetch',side_effect=responses):
            results,source=restaurants.osm('中餐餐廳','Walnut, CA')
        self.assertEqual(results[0]['name'],'Test fixture only')
        self.assertNotIn('rating',results[0])
        self.assertIn('OpenStreetMap',source)

    def test_failure_does_not_invent(self):
        with patch.object(restaurants,'osm',side_effect=TimeoutError), \
             patch.dict(restaurants.os.environ,{'GOOGLE_PLACES_API_KEY':''}), \
             patch.object(restaurants.Path,'is_file',return_value=False):
            result=restaurants.search('附近餐廳')
        self.assertIn('沒有可驗證的店家結果',result['display'])
        self.assertIn('https://www.google.com/maps/search/',result['display'])


if __name__=='__main__':
    unittest.main()
