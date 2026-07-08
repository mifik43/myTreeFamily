from flask import session, current_app
from flask_login import current_user
from models import Tree, Person, db, GeoCache
import requests


def get_active_tree():
    if not current_user.is_authenticated:
        return None
    tree_id = session.get('active_tree_id')
    if tree_id:
        tree = Tree.query.get(tree_id)
        if tree and any(p.user_id == current_user.id for p in tree.permissions):
            return tree
    for perm in current_user.tree_permissions:
        if perm.role in ('owner', 'editor'):
            session['active_tree_id'] = perm.tree_id
            return perm.tree
    return None

def get_active_persons(tree_id=None):
    """Возвращает запрос, исключающий мягко удалённых персон."""
    q = Person.query.filter(Person.deleted_at == None)
    if tree_id is not None:
        q = q.filter(Person.tree_id == tree_id)
    return q

def geocode(place_name):
    """Геокодирует название места через Яндекс.Геокодер, используя кеш."""
    if not place_name:
        return None, None

    cached = GeoCache.query.filter_by(place_name=place_name).first()
    if cached:
        return cached.latitude, cached.longitude

    api_key = current_app.config.get('YANDEX_MAPS_API_KEY')
    if not api_key:
        return None, None

    url = 'https://geocode-maps.yandex.ru/1.x/'
    params = {
        'apikey': api_key,
        'geocode': place_name,
        'format': 'json',
        'results': 1,
        'lang': 'ru_RU',
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        geo_collection = data.get('response', {}).get('GeoObjectCollection', {})
        features = geo_collection.get('featureMember', [])
        if features:
            pos_str = features[0]['GeoObject']['Point']['pos']
            lon, lat = pos_str.split()  # у Яндекса порядок: долгота широта
            lat, lon = float(lat), float(lon)
            cache_entry = GeoCache(place_name=place_name, latitude=lat, longitude=lon)
            db.session.add(cache_entry)
            db.session.commit()
            return lat, lon
    except Exception:
        pass
    return None, None