"""Live restaurant lookup: Google Places if configured, otherwise OpenStreetMap.
No claims of taste, verified opening status, or user-relative distance without data.
"""
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UA = 'Neris-A/0.1 (personal local restaurant lookup)'


def fetch(url, data=None, headers=None, timeout=25):
    request = urllib.request.Request(url, data=data, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def location():
    home = json.loads((ROOT / 'location.json').read_text())['home']
    return home['display_name']


def google(query, area, key):
    data = fetch('https://places.googleapis.com/v1/places:searchText',
        data=json.dumps({'textQuery': f'{query} restaurants near {area}', 'pageSize': 5,
                         'languageCode':'zh-TW'}).encode(),
        headers={'Content-Type':'application/json','X-Goog-Api-Key':key,
                 'X-Goog-FieldMask':'places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.googleMapsUri,places.currentOpeningHours.openNow,places.priceLevel'})
    results=[]
    for place in data.get('places',[]):
        results.append({'name':place.get('displayName',{}).get('text','Unnamed restaurant'),
            'address':place.get('formattedAddress',''), 'rating':place.get('rating'),
            'reviews':place.get('userRatingCount'), 'url':place.get('googleMapsUri',''),
            'open':place.get('currentOpeningHours',{}).get('openNow'),
            'price':place.get('priceLevel')})
    return results, 'Google Places'


def km(lat1, lon1, lat2, lon2):
    a,b=math.radians(lat1),math.radians(lat2)
    x=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(x)))


def osm(query, area):
    # Geocode only the user-provided city, not their precise location.
    params=urllib.parse.urlencode({'q':area,'format':'jsonv2','limit':1,'countrycodes':'us'})
    locations=fetch('https://nominatim.openstreetmap.org/search?'+params)
    if not locations:
        raise ValueError('City center not found')
    lat,lon=float(locations[0]['lat']),float(locations[0]['lon'])
    cuisine=None
    for words,tag in [(('中餐','中式','chinese'),'chinese'),(('日式','日本','japanese'),'japanese'),
                      (('韓式','韓國','korean'),'korean'),(('泰式','泰國','thai'),'thai'),
                      (('越南','vietnamese'),'vietnamese'),(('墨西哥','mexican'),'mexican'),
                      (('義大利','意大利','italian'),'italian'),(('披薩','pizza'),'pizza'),
                      (('台菜','台式','taiwanese'),'taiwanese')]:
        if any(word in query.lower() for word in words):
            cuisine=tag;break
    selector='["amenity"="restaurant"]'
    if cuisine:
        selector+=f'["cuisine"~"(^|;){cuisine}(;|$)"]'
    statement=f'[out:json][timeout:15];nwr(around:5000,{lat},{lon}){selector};out center tags 100;'
    data=fetch('https://overpass-api.de/api/interpreter',
        data=urllib.parse.urlencode({'data':statement}).encode(),timeout=22)
    results=[]
    for element in data.get('elements',[]):
        tags=element.get('tags',{})
        if not tags.get('name'):continue
        center=element.get('center',element)
        distance=km(lat,lon,float(center['lat']),float(center['lon']))
        address=' '.join(tags.get(key,'') for key in ('addr:housenumber','addr:street','addr:city')).strip()
        results.append({'name':tags['name'],'address':address,'cuisine':tags.get('cuisine'),
                        'hours':tags.get('opening_hours'),'km':distance,
                        'url':f"https://www.openstreetmap.org/{element['type']}/{element['id']}"})
    results.sort(key=lambda item:item['km'])
    return results[:5], 'OpenStreetMap / Nominatim / Overpass'


def is_request(text):
    lowered=text.lower()
    return any(word in lowered for word in ('餐廳','餐厅','restaurant','附近有什麼好吃','附近有啥好吃','附近吃什麼','附近吃什么'))


def search(query):
    try:
        area=location()
        key=os.environ.get('GOOGLE_PLACES_API_KEY')
        key_file=ROOT/'private/google-places-key.txt'
        if not key and key_file.is_file():
            key=key_file.read_text().strip()
        results,source=google(query,area,key) if key else osm(query,area)
        stamp=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
        lines=[f'餐廳搜尋區域：{area}',f'來源：{source}；查詢時間：{stamp}']
        if not key:
            lines.append('範圍：城市中心約5公里；依中心距離排序，不是好吃程度排名。OSM無評分/價位，營業時間是登錄文字，未驗證現在是否營業。只支援部分菜系篩選；其他預算/營業中條件未套用。')
        for index,item in enumerate(results,1):
            lines.append(f"\n{index}. {item['name']}")
            if item.get('address'):lines.append('地址：'+item['address'])
            if 'km' in item:lines.append(f"距城市中心約{item['km']:.1f}公里（非你目前位置）")
            if item.get('cuisine'):lines.append('菜系：'+item['cuisine'])
            if item.get('rating') is not None:lines.append(f"評分：{item['rating']}；評論數：{item.get('reviews','未提供')}")
            if item.get('open') is not None:lines.append('服務回報目前營業：'+('是' if item['open'] else '否')+'，出發前請再確認')
            if item.get('price'):lines.append('價位：'+item['price'])
            if item.get('hours'):lines.append('登錄營業時間：'+item['hours'])
            if item.get('url'):lines.append(item['url'])
        if not results:
            lines.append('本次資料來源未找到符合店家，不代表當地沒有餐廳。')
        link='https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote(query+' '+area)
        lines.extend(['\n可另開地圖查詢：',link])
        speech=(f"查到{len(results)}家餐廳，包括"+'、'.join(item['name'] for item in results[:3])+ '。詳細資料在對話框，營業資訊請再確認。') if results else '這次資料來源沒找到符合的餐廳，地圖搜尋連結已放在對話框。'
        return {'display':'\n'.join(lines),'speech':speech}
    except Exception as error:
        # No secrets or raw provider response are exposed to the conversation.
        area='Walnut, CA'
        link='https://www.google.com/maps/search/?api=1&query='+urllib.parse.quote(query+' '+area)
        return {'display':f'即時餐廳查詢未完成（{type(error).__name__}），沒有可驗證的店家結果。\n可手動開地圖：\n{link}',
                'speech':'即時餐廳查詢暫時失敗，我沒有可靠的店家結果，已把地圖搜尋連結放在對話框。'}
