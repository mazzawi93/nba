import operator
import string
from random import shuffle

import pandas as pd
from pymongo import MongoClient

from db import process_data
from db import process_utils


def dc_dataframe(season=None, month=None, bet=False):
    """
    Create a Pandas DataFrame for the Dixon and Coles model that uses final scores only.
    Can specify the NBA season, month and if betting information should be included.

    :param season: NBA Season
    :param month: Calendar Month
    :param bet: Betting Lines
    :return: Pandas DataFrame
    """

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    fields = {
        'home': '$home.team',
        'away': '$away.team',
        'hpts': '$home.pts',
        'apts': '$away.pts',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2012]}, 52]}]},
        'date': 1,
    }

    match = {}

    process_utils.season_check(season, fields, match)
    process_utils.month_check(month, fields, match)

    if bet:
        fields['hbet'] = '$bet.home'
        fields['abet'] = '$bet.away'

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = collection.aggregate(pipeline, allowDiskUse=True)

    df = pd.DataFrame(list(games))

    # Remove unnecessary information
    del df['_id']
    del df['season']
    del df['date']

    return df


def game_scores(season=None, month=None, bet=False):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored.

    :param month: Calendar Month
    :param season: NBA Season (All stored season selected if None)
    :return: Pandas Dataframe
    """

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    # Fields we need from mongoDB no matter what the search fields are
    fields = {
        'home.team': 1,
        'away.team': 1,
        'home.pts': 1,
        'away.pts': 1,
        'home_time.points': 1,
        'home_time.time': 1,
        'away_time.points': 1,
        'away_time.time': 1,
        'date': 1,
        'bet': 1
    }

    match = {}

    # Prepare season value
    process_utils.season_check(season, fields, match)
    process_utils.month_check(month, fields, match)

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = collection.aggregate(pipeline, allowDiskUse=True)

    matches = []

    for game in games:

        # Add the time for each point if wanted
        point_list = []

        home_score = 0
        for stat in game['home_time']:
            if 'points' in stat:
                time = float(stat['time'])
                if time <= 48:
                    stat['home'] = 1
                    point_list.append(stat)
                    home_score += stat['points']

        away_score = 0
        for stat in game['away_time']:
            if 'points' in stat:
                time = float(stat['time'])
                if time <= 48:
                    stat['home'] = 0
                    point_list.append(stat)
                    away_score += stat['points']

        point_list.sort(key=operator.itemgetter('time'))

        match = {'home': game['home']['team'],
                 'away': game['away']['team'],
                 'home_pts': home_score,
                 'away_pts': away_score,
                 'time': point_list}

        # Add betting lines
        if bet:
            try:
                match['home_bet'] = float(game['bet']['home'])
                match['away_bet'] = float(game['bet']['away'])
            except KeyError:
                match['home_bet'] = 1.0
                match['away_bet'] = 1.0

        matches.append(match)

    result = pd.DataFrame(matches)

    return result


def create_test_set(t, g, margin, bet=False, point_times=True):
    """
    Create test set based on the number of teams and games played per team.
    Games are taken from the game_log mongodb collection based on the winning
    margin.  Games will only be selected once to have a unique test set.

    This test set will be used to validate the model because the first team
    will be the strongest, second will be second strongest and so on.

    :param t: The number of teams
    :param g: The number of games played between a set of two teams (Must be even.)
    :param margin: The winning margin
    :return: Pandas Dataframe containing data (Points per team (total and time stamps))
    """

    if t < 2:
        raise ValueError('There must be at least two teams.')

    # G must be even so that there is an equal number of home and away games
    if g % 2 != 0:
        raise ValueError('The number of games must be even so there is equal home and away')

    data = []
    teams = []

    # Ids of games taken from MongoDB
    ids = []

    print("Creating Test Set...")

    # Give out team names in order so we always know the order of strength
    for i in range(t):
        if i < 26:
            teams.append(string.ascii_uppercase[i])
        else:
            teams.append(string.ascii_uppercase[i - 26] + string.ascii_uppercase[i - 26])

    x = 0
    for team in teams:

        # Iterate through the teams so that each team plays each other n times.
        # The teams play each other the same amount at home and away
        for i in range(t - 1, x, -1):

            # The number of games two teams play against each other
            for j in range(g):

                game = {}

                # Split matches so teams are playing home and away evenly
                if j % 2 == 0:
                    game['home'] = team
                    game['away'] = teams[i]
                    match = process_data.select_match(margin, ids)
                else:
                    game['home'] = teams[i]
                    game['away'] = team
                    match = process_data.select_match(-margin, ids)

                if point_times:

                    point_list = []

                    home_score = 0
                    for stat in match['home_time']:
                        if 'points' in stat:
                            time = float(stat['time'])
                            if time <= 48:
                                stat['home'] = 1
                                point_list.append(stat)
                                home_score += stat['points']

                    away_score = 0
                    for stat in match['away_time']:
                        if 'points' in stat:
                            time = float(stat['time'])
                            if time <= 48:
                                stat['home'] = 0
                                point_list.append(stat)
                                away_score += stat['points']

                    point_list.sort(key=operator.itemgetter('time'))

                    game['time'] = point_list
                    game['hpts'] = home_score
                    game['apts'] = away_score
                else:
                    game['hpts'] = match['home']['pts']
                    game['apts'] = match['away']['pts']

                if bet:
                    try:
                        game['hbet'] = float(match['bet']['home'])
                        game['abet'] = float(match['bet']['away'])
                    except KeyError:
                        game['hbet'] = 1.0
                        game['abet'] = 1.0

                # Append the id to the list so that the match doesn't get selected again
                ids.append(match['_id'])

                data.append(game)

        x += 1

    shuffle(data)
    return pd.DataFrame(data)
