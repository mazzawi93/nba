import json
from datetime import datetime

import pandas as pd
from bson import json_util
from pandas.io.json import json_normalize
from pymongo import MongoClient
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


def split_game_data(collection):
    train_date = datetime(2016, 7, 30)

    train = collection.find({'date': {"$lte": train_date}}).sort("date")
    test = collection.find({'date': {"$gte": train_date}}).sort("date")
    print(train.count() + test.count())

    sanitized = json.loads(json_util.dumps(train))
    normalized = json_normalize(sanitized)
    df_train = pd.DataFrame(normalized)

    sanitized = json.loads(json_util.dumps(test))
    normalized = json_normalize(sanitized)
    df_test = pd.DataFrame(normalized)

    items = ['_id.$oid', 'date.$date', 'home.team', 'away.team', 'away_season.avg_ht', 'home_season.avg_ht', 'home.score', 'away.score']
    # drop teams if in there
    df_test.drop(items, axis=1, inplace=True)
    df_train.drop(items, axis=1, inplace=True)

    df_train = df_train.dropna()
    df_test = df_test.dropna()

    y_train = df_train.pop('result')
    y_test = df_test.pop('result')

    model = ExtraTreesClassifier()
    model.fit(df_train, y_train)

    stats = list(df_train)

    x = 0
    to_drop = []
    for feature in model.feature_importances_:
        if feature < 0.009:
            to_drop.append(stats[x])
        x += 1

    df_test.drop(to_drop, axis=1, inplace=True)
    df_train.drop(to_drop, axis=1, inplace=True)

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
    print("%s - Naive Bayes" % clf.score(data['test']['x'], data['test']['y']))


def k_nearest_neighbours(data):
    knn = KNeighborsClassifier()
    knn.fit(data['train']['x'], data['train']['y'])
    print("%s - K Nearest Neighbours" % knn.score(data['test']['x'], data['test']['y']))


def support_vector_machine(data):
    svm = SVC()
    svm.fit(data['train']['x'], data['train']['y'])
    print("%s - SVM" % svm.score(data['test']['x'], data['test']['y']))


def decision_tree(data):
    dtc = DecisionTreeClassifier()
    dtc.fit(data['train']['x'], data['train']['y'])
    print("%s - Decision Trees" % dtc.score(data['test']['x'], data['test']['y']))


client = MongoClient()
db = client.basketball
collection_process = db.game_preprocess
collection_game = db.game_log

df = split_game_data(collection_process)
naive_bayes(df)
k_nearest_neighbours(df)
support_vector_machine(df)
decision_tree(df)

client.close()
