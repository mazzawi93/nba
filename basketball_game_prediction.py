from pymongo import MongoClient
from datetime import datetime
import pandas as pd
import json
from bson import json_util
from pandas.io.json import json_normalize
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

client = MongoClient()
db = client.basketball
collection_game_log = db.game_log
collection_players = db.player


def split_game_data(collection):
    train_date = datetime(2016, 7, 30)

    train = collection.find({'date': {"$lte": train_date}}).sort("date")
    test = collection.find({'date': {"$gte": train_date}}).sort("date")

    sanitized = json.loads(json_util.dumps(train))
    normalized = json_normalize(sanitized)
    df_train = pd.DataFrame(normalized)

    sanitized = json.loads(json_util.dumps(test))
    normalized = json_normalize(sanitized)
    df_test = pd.DataFrame(normalized)

    df_test.drop(['_id.$oid', 'date.$date', 'home.team', 'away.team'], axis=1, inplace=True)
    df_train.drop(['_id.$oid', 'date.$date', 'home.team', 'away.team'], axis=1, inplace=True)

    y_train = df_train.pop('home_result')
    y_test = df_test.pop('home_result')

    data = {
        'train': {
            'x': df_train,
            'y': y_train
        },
        'test': {
            'x': df_test,
            'y': y_test
        }
    }

    return data


def naive_bayes(data):
    clf = GaussianNB()
    clf.fit(data['train']['x'], data['train']['y'])
    print(clf.score(data['test']['x'], data['test']['y']))


def k_nearest_neighbours(data):
    knn = KNeighborsClassifier()
    knn.fit(data['train']['x'], data['train']['y'])
    print(knn.score(data['test']['x'], data['test']['y']))


def support_vector_machine(data):
    svm = SVC()
    svm.fit(data['train']['x'], data['train']['y'])
    print(svm.score(data['test']['x'], data['test']['y']))


def decision_tree(data):
    dtc = DecisionTreeClassifier()
    dtc.fit(data['train']['x'], data['train']['y'])
    print(dtc.score(data['test']['x'], data['test']['y']))


df = split_game_data(collection_game_log)
naive_bayes(df)
k_nearest_neighbours(df)
support_vector_machine(df)
decision_tree(df)
