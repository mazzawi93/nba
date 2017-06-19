import operator
import pandas as pd
from pymongo import MongoClient

stat_names = ['orb', 'drb', 'fgm', 'fga', 'assist', 'points', 'ftm', 'fta',
              'fg3a', 'fg3m', 'turnover', 'foul', 'timeout', 'sub']

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA',
         'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']

seasons = [2012, 2013, 2014, 2015, 2016, 2017]





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
