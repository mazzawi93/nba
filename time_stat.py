import operator
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


def match_point_times(season=None, team=None, home_win=None):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored (divided by 48 so the times are (0, 1]).

    :param home_win:
    :param team: NBA Team (All teams selected if None)
    :param season: NBA Season (All stored season selected if None)
    :return: Pandas Dataframe
    """

    # Check season values
    season = season_check(season)

    # Check team values
    team = team_check(team)

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

    games = collection.find({'result': {'$in': result}, 'season': {'$in': season}, '$or': [{'home.team': {'$in': team}},
                                                                                           {'away.team': {
                                                                                               '$in': team}}]},
                            criteria).sort('date')
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

        print(match)

        matches.append(match)

    result = pd.DataFrame(matches)

    return result


def select_match(win_margin):
    """
    Select a match from game logs with a winning margin.
    :param win_margin: Win margin of the game, negative means the away team won.
    :return: The game selected from MongoDB
    """

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    pipeline = [
        {'$project':
             {'home_time.points': 1,
              'away_time.points': 1,
              'home_time.time': 1,
              'away_time.time': 1,
              'home.pts': 1,
              'away.pts': 1,
              'difference': {'$subtract': ['$home.pts', '$away.pts']}
              }},
        {'$match': {'difference': {'$eq': win_margin}}},
        {'$limit': 1}
    ]

    game = collection.aggregate(pipeline)

    # The limit is 1, so just return the first object
    for i in game:
        return i
