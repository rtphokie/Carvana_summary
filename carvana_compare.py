import re
import pandas as pd
import json
from pathlib import Path
import requests_cache, requests

# Show all columns
pd.set_option('display.max_columns', None)

# Use the full width of the screen
pd.set_option('display.width', None)
pd.set_option('display.expand_frame_repr', False)
import warnings
import urllib3

warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)
headers = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15'}


def read_strings_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        lines = [line.strip() for line in file if line.strip()]
    return lines


def carvana_vehicle_fetch(vehicleId, cache_name='web_cache', expire_after=3600):
    session = requests_cache.CachedSession(cache_name=cache_name, expire_after=expire_after)
    url = f'https://apim.carvana.io/vehicle-details-api/api/v1/vehicledetails?vehicleId={vehicleId}'

    r = session.get(url, headers=headers)
    if not r.from_cache:
        print(f'{vehicleId} not from cache')
    res = json.loads(r.text)
    return res


def find_common_items(list_of_lists):
    if not list_of_lists:
        return []

    # Convert each sublist to a set and compute intersection
    common_items = set(list_of_lists[0])
    for lst in list_of_lists[1:]:
        common_items &= set(lst)

    return list(common_items)


def fetch_vehicle(all_features, features, imperfection_count, vehicleId):
    data = carvana_vehicle_fetch(vehicleId)
    features[vehicleId] = []
    filepath = f"json/{vehicleId}.json"
    for feature in data['header']['gallery']['spinnerData']['features']:
        features[vehicleId].append(feature['title'])
        all_features.add(feature['title'])
    for hotspot in data['header']['gallery']['hotspots']:
        if hotspot['type'] == 'imperfection':
            attr = hotspot['title']
            if attr in ['"Tire Inflator Kit"']:
                continue
            if 'imperfectionLevel' in hotspot:
                attr = f"{attr} {hotspot['imperfectionLevel']}"
            imperfection_count[attr] = 0
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return data


def process_basics(data, feature_present, result, vehicleId):
    for attr in ['year', 'trim', 'mileage', 'price', 'kbbValue']:
        result[vehicleId][attr] = data['header'][attr]
    result[vehicleId][
        'location'] = f"{data['header']['location']['city']}, {data['header']['location']['stateAbbreviation']}"
    for attr in ['msrp', 'vin', 'exteriorColor', 'interiorColor', 'engineDescription']:
        if attr in data['details']['basics']:
            result[vehicleId][attr] = data['details']['basics'][attr]
    if 'msrp' in data['details']['basics']:
        result[vehicleId]['discount'] = round(data['details']['basics']['msrp'] - data['header']['price'])
    else:
        result[vehicleId]['discount'] = None
    result[vehicleId].update(feature_present.copy())


def process_scratches_and_dents(data, imperfection_count, result, uninteresting_features, vehicleId):
    result[vehicleId].update(imperfection_count.copy())
    for hotspot in data['header']['gallery']['hotspots']:
        if hotspot['type'] == 'imperfection':
            attr = hotspot['title']
            if attr in uninteresting_features:
                continue
            result[vehicleId]['total'] += 1
            if 'imperfectionLevel' in hotspot:
                attr = f"{attr} {hotspot['imperfectionLevel']}"
            result[vehicleId][attr] += 1


def process_features(data, interesting_features, result, vehicleId):
    uninteresting_features = read_strings_from_file("uninteresting_features.txt")

    for feature in data['header']['gallery']['spinnerData']['features']:
        if feature['title'] in interesting_features:
            result[vehicleId][feature['title']] = True

        if feature['title'] == 'keys':
            match = re.search(r'\d+', feature['description'])
            if match:
                number = int(match.group())
                result[vehicleId]['keys'] = number

        for highlight in data['vdpHighlights']:
            if highlight['name'] not in uninteresting_features:
                result[vehicleId][highlight['name']] = True


def main():
    vehicle_ids = read_strings_from_file("carvana_ids.txt")
    features = {}
    all_features = set()
    imperfection_count = {'total': 0}

    # fetch 'em and cache 'em, gather features
    for vehicleId in vehicle_ids:
        fetch_vehicle(all_features, features, imperfection_count, vehicleId)

    uninteresting_features = read_strings_from_file("uninteresting_features.txt")
    common_features = find_common_items(list(features.values()))
    interesting_features = all_features - set(common_features) - set(uninteresting_features)

    feature_present = {}
    for feature in read_strings_from_file("feature_priority.txt"):
        feature_present[feature] = None
    feature_present['keys'] = None
    for feature in interesting_features:
        if feature not in feature_present:
            feature_present[feature] = None

    result = {}
    for vehicleId in vehicle_ids:
        # should already be cached
        data = fetch_vehicle(all_features, features, imperfection_count, vehicleId)
        if data['header']['purchaseType'] not in ['Purchasable']:
            continue  # sale pending
        if data['header']['isRental']:
            continue  # not worth the risk

        result[vehicleId] = {'url': f"https://www.carvana.com/vehicle/{vehicleId}"}

        process_basics(data, feature_present, result, vehicleId)

        process_features(data, interesting_features, result, vehicleId)

        process_scratches_and_dents(data, imperfection_count, result, uninteresting_features, vehicleId)

    df = pd.DataFrame.from_dict(result, orient='index')
    filename='carvana_result.csv'
    df.to_csv(filename)
    print(f"wrote {df.shape[0]} rows to {filename}")


if __name__ == '__main__':
    Path("json").mkdir(exist_ok=True)
    main()
