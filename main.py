import requests
from math import sqrt, tanh
import operator
import pickle

API_KEY = "" #fuck you get your own

def get_user_ratings(userid, apikey = API_KEY, year=None, score=None):
    url = f"https://omdb.nyahh.net/api/user/{userid}/ratings?key={apikey}"
    if year:
        url += f"&year={year}"
    if score:
        url += f"&score={score}"
    response = requests.get(url)
    return response.json()

def get_beatmap_details(beatmapid, apikey = API_KEY):
    url = f"http://omdb.nyahh.net/api/beatmap/{beatmapid}?key={apikey}"
    response = requests.get(url)
    return response.json()

def z_score(x):
    mean = sum(x.values())/len(x)
    standard_deviation = (sum([(value-mean)**2 for value in x.values()])/len(x))**0.5
    z_scores = {key: (value - mean)/standard_deviation for key, value in x.items()}
    return z_scores, mean, standard_deviation

class User: #wrote this before realizing i really do not need to make unique objects for each user but i dont care
    def __init__(self, user_id: int):
        self.id = user_id
        self.ratings = {}
        self.mean, self.std = None, None
        self.get_ratings()

    def get_ratings(self, apikey = API_KEY):
        ratings = get_user_ratings(self.id, apikey)
        for rating in ratings:
            beatmap_id = rating['BeatmapID']
            score = float(rating['Score']) #api stores as string to avoid floating point nonsense
            self.ratings[beatmap_id] = score
        self.ratings, self.mean, self.std = z_score(self.ratings) #normalize ratings to measure in terms of z score rather than rating cuz ppls distributions r different
        return self

def cosine_similarity(a, b): #might be a better comparison but idc
    dot_product = sum(a * b for a, b in zip(a, b))
    m1 = sqrt(sum(a ** 2 for a in a))
    m2 = sqrt(sum(b ** 2 for b in b))
    return dot_product / (m1 * m2)

def find_similar_users(target_user, user_array, N = 5): #theres a buncha techniques used in ml to make this faster but i am lazy so ill leave like this for now
    target_ratings = target_user.ratings
    target_user_keys = set(target_ratings.keys())
    similar_users = []
    for other_user in user_array:
        if target_user.id == other_user.id: #ur obviously gonna have similar rating to urself so we skip
            continue
        other_ratings = other_user.ratings
        other_user_keys = set(other_ratings.keys())
        common_keys = target_user_keys & other_user_keys
        common = tanh(len(common_keys) / 120) #scaling factor based on how many maps u have rated in common, there is no justification behind tanh and 120 i just made them up lol
        if not common_keys:
            continue
        a = [target_ratings[key] for key in common_keys]
        b = [other_ratings[key] for key in common_keys]
        similarity = common * cosine_similarity(a, b)
        similar_users.append((other_user, similarity))

    similar_users.sort(key=operator.itemgetter(1), reverse=True)
    return similar_users[:N]

user_array = []
id_array = [7704651,9558549,8589120,4323406,7127366,5991961,7535045,15545399,
            17635061,1343783,4209965,7712676,3792472,13083042,4330511,3533958,
            4485933,3087506,4437004,4994598,10321729,9948665,10321729,3388082,
            4859362,3181083,11106929,1721120] #buncha random ppl i saw had rated some maps

def initialize_users(user_ids):
    users = [User(user_id) for user_id in user_ids] #make an array of user objects
    return users

def write_db():
    with open('db.pickle', 'wb') as handle:
        pickle.dump(user_array, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return None

def read_db():
    with open('db.pickle', 'rb') as handle:
        users = pickle.load(handle)
    return users

try:
    user_array = read_db() #this shit takes AGES so i store results in db.pickle, i would make this better but lazy
except:
    user_array += initialize_users(id_array)
    write_db()

MIN_WEIGHT = 0.9 # minimum cumulative similarity for a beatmap to show up as recommended

def recommend_beatmaps(target_user, similar_users, n=5):
    target_beatmaps = set(target_user.ratings.keys())
    recommended_beatmaps = {}
    total_weights = {}
    for similar_user, similarity in similar_users[:n]:
        for beatmap_id, rating in similar_user.ratings.items():
            if beatmap_id in target_beatmaps:
                continue
            if beatmap_id not in recommended_beatmaps:
                recommended_beatmaps[beatmap_id] = 0
                total_weights[beatmap_id] = 0
            recommended_beatmaps[beatmap_id] += similarity * rating
            total_weights[beatmap_id] += similarity #since we want to calculate the expected deviation rather than total, we sum up similarities so we can divide by them (or disregard if not above threshold)
    recommended_beatmaps = [(beatmap_id, score / total_weights[beatmap_id]) for beatmap_id, score in recommended_beatmaps.items() if total_weights[beatmap_id] > MIN_WEIGHT]
    recommended_beatmaps.sort(key=lambda x: x[1], reverse=True)
    return recommended_beatmaps[:n]

user = User(9558549) #hi apollo
similar = find_similar_users(user, user_array, 10) 
maps = recommend_beatmaps(user, similar, 10)

for user, similarity in similar:
    print(f"User ID: {user.id} - Similarity: {similarity}")

for id, zscore in maps:
    curr_map = get_beatmap_details(id)
    expected_rating = "{:.2f}".format(min(max(user.std*zscore+user.mean,0.00),5.00)) #yes i know u can only rate in .5 intervals but this is cooler
    current_rating = "{:.2f}".format(curr_map['WeightedAvg']) if curr_map['WeightedAvg'] else "None"
    print(f"https://osu.ppy.sh/beatmapsets/{curr_map['SetID']}  ||  {curr_map['Artist']} - {curr_map['Title']} [{curr_map['Difficulty']}] || Estimated: {expected_rating} - Current: {current_rating} ")
    

