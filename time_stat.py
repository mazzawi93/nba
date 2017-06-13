import operator

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pymongo import MongoClient

stat_names = ['orb', 'drb', 'fgm', 'fga', 'assist', 'points', 'ftm', 'fta',
              'fg3a', 'fg3m', 'turnover', 'foul', 'timeout', 'sub']

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA',
         'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']

seasons = [2012, 2013, 2014, 2015, 2016, 2017]


def season_check(season):
    """
    Helper function to determine if season is correctly entered
    :param season: List of seasons or None
    :return: Season List
    """

    if not isinstance(season, list):
        if season is not None:
            raise TypeError("Season must be a list for query purposes")
        else:
            return [2012, 2013, 2014, 2015, 2016, 2017]
    else:
        for year in season:
            if year < 2012 or year > 2017:
                raise ValueError("Years must be within the range 2012-2017")

    return season


def team_check(team):
    """
    Helper function to determine if teams were entered correctly
    :param team: List of NBA Teams
    :return: List of Teams
    """
    if not isinstance(team, list):
        if team is not None:
            raise TypeError("Team must be a list for query purposes")
        else:
            team = teams
    else:
        for city in team:
            if city not in teams:
                raise ValueError("Team not in database")

    return team


def point_time_dist(season=None, team=None, home=None, home_win=None):
    """

    :param season: List of seasons
    :param team: List of teams
    :param home: Boolean for home or away (None for both)
    :param home_win: Boolean for Home or Away Win (None to include both)
    :return: Point Distribution by the minute
    """
    time_data = {}

    # Check season values
    season = season_check(season)

    # Check team values
    team = team_check(team)

    # Check Home Value
    if not isinstance(home, bool):
        if home is not None:
            raise TypeError("Home must be a Boolean value or None")

    # Check Home Win Value
    if not isinstance(home_win, bool):
        if home_win is not None:
            raise TypeError("Home Win must be a Boolean value or None")

    if home_win is None:
        result = [1, -1]
    elif home_win is True:
        result = [1]
    else:
        result = [-1]

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    if home is None:
        locations = ['home_time', 'away_time']
        games = collection.find(
            {'result': {'$in': result}, 'season': {'$in': season},
             '$or': [{'home.team': {'$in': team}}, {'away.team': {'$in': team}}]},
            {'home_time': 1, 'away_time': 1})
    elif home is True:
        locations = ['home_time']
        games = collection.find({'result': {'$in': result}, 'season': {'$in': season}, 'home.team': {'$in': team}},
                                {'home_time': 1})
    else:
        locations = ['away_time']
        games = collection.find({'result': {'$in': result}, 'season': {'$in': season}, 'away.team': {'$in': team}},
                                {'away_time': 1})

    print('Processing Time Data')

    for game in games:
        for loc in locations:
            for stat in game[loc]:

                time = int(stat['time']) + 1

                # Only want regulation time
                if time <= 48:
                    for key in ['points']:
                        if key in stat:

                            if time not in time_data:
                                time_data[time] = {}

                            if key not in time_data[time]:
                                time_data[time][key] = stat[key]

                            else:
                                time_data[time][key] = time_data[time][key] + stat[key]

    data = pd.DataFrame(time_data)
    data = data.transpose()

    return data


def match_point_times(season=None, team=None):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored (divided by 48 so the times are (0, 1]).

    :param team: NBA Team (All teams selected if None)
    :param season: NBA Season (All stored season selected if None)
    :return: Pandas Dataframe
    """

    # Check season values
    season = season_check(season)

    # Check team values
    team = team_check(team)

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    criteria = {
        'home.team': 1,
        'home.pts': 1,
        'away.team': 1,
        'away.pts': 1,
        'home_time.points': 1,
        'home_time.time': 1,
        'away_time.points': 1,
        'away_time.time': 1,
        '_id': 0
    }

    games = collection.find({'season': {'$in': season}, '$or': [{'home.team': {'$in': team}},
                                                                {'away.team': {'$in': team}}]}, criteria).sort('date')
    matches = []

    for game in games:

        point_times = []

        home_score = 0
        for stat in game['home_time']:
            if 'points' in stat:
                if stat['time'] <= 48:
                    stat['time'] = round(stat['time'] / 48, 4)
                    stat['home'] = 1
                    home_score += stat['points']
                    point_times.append(stat)

        away_score = 0
        for stat in game['away_time']:
            if 'points' in stat:
                if stat['time'] <= 48:
                    stat['time'] = round(stat['time'] / 48, 4)
                    stat['home'] = 0
                    away_score += stat['points']
                    point_times.append(stat)

        point_times.sort(key=operator.itemgetter('time'))

        match = {'home': game['home']['team'],
                 'away': game['away']['team'],
                 'home_pts': home_score,
                 'away_pts': away_score,
                 'time': point_times}

        matches.append(match)

    result = pd.DataFrame(matches)

    return result


def score_hist(season=None, team=None):
    # Check season values
    season = season_check(season)

    # Check team values
    if not isinstance(team, list):
        if team is not None:
            raise TypeError("Team must be a list for query purposes")
        else:
            team = teams
    else:
        for city in team:
            if city not in teams:
                raise ValueError("Team not in database")

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    criteria = {
        'home.pts': 1,
        'away.pts': 1,
        '_id': 0
    }

    search = {'season': {'$in': season}, '$or': [{'home.team': {'$in': team}},
                                                 {'away.team': {'$in': team}}]}

    games = collection.find(search, criteria)

    max_min_pts = collection.aggregate([
        {'$match': {'season': 2016}},
        {'$group': {
            '_id': None,
            'max_home': {'$max': '$home.pts'},
            'max_away': {'$max': '$away.pts'}
        }}
    ])

    maxh, maxa = 0, 0

    for pts in max_min_pts:
        maxh, maxa = pts['max_home'], pts['max_away']

    home = np.zeros(maxh + 1)
    away = np.zeros(maxa + 1)

    for game in games:
        home[game['home']['pts']] += 1
        away[game['away']['pts']] += 1

    print(home)
    print(away)
    np.histogram(home)

    plt.hist(home)
    plt.show()

