import operator
import string
from random import shuffle
import pandas as pd
from pymongo import MongoClient

from db import process_data


def match_point_times(season=None, month=None):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored (divided by 48 so the times are (0, 1]).

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
        'home_time.points': 1,
        'home_time.time': 1,
        'away_time.points': 1,
        'away_time.time': 1,
        'date': 1
    }

    match = {}

    # Prepare season value
    if season is not None:

        # Convert season to list because aggregation uses $in
        if isinstance(season, int):
            season = [season]

        # Raise error if incorrect type was given
        if not isinstance(season, list):
            raise TypeError("Season must be a list for query purposes")
        else:
            # Raise error if year value is incorrect
            for year in season:
                if year < 2012 or year > 2017:
                    raise ValueError("Years must be within the range 2012-2017")

            # Add season for aggregation query
            fields['season'] = 1
            match['season'] = {'$in': season}

    if month is not None:
        if isinstance(month, int):
            month = [month]

        if not isinstance(month, list):
            raise TypeError("Incorrect type entered for month (int or list)")

        fields['month'] = {'$month': '$date'}
        match['month'] = {'$in': month}

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = collection.aggregate(pipeline, allowDiskUse=True)

    matches = []

    for game in games:

        # Store all points by the minute instead of all individually
        point_dict = {}

        home_score = 0
        for stat in game['home_time']:
            if 'points' in stat:
                time = int(stat['time']) + 1
                if time <= 48:

                    if time not in point_dict:
                        point_dict[time] = {'home': 0, 'away': 0, 'time': time}

                    point_dict[time]['home'] += stat['points']
                    home_score += stat['points']

        away_score = 0
        for stat in game['away_time']:
            if 'points' in stat:
                time = int(stat['time']) + 1
                if time <= 48:

                    if time not in point_dict:
                        point_dict[time] = {'home': 0, 'away': 0, 'time': time}

                    point_dict[time]['away'] += stat['points']
                    away_score += stat['points']

        point_list = [v for v in point_dict.values()]
        point_list.sort(key=operator.itemgetter('time'))

        match = {'home': game['home']['team'],
                 'away': game['away']['team'],
                 'home_pts': home_score,
                 'away_pts': away_score,
                 'time': point_list}

        matches.append(match)

    result = pd.DataFrame(matches)

    return result


def create_test_set(t, g, margin):
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

                # Store all points by the minute instead of all individually
                point_dict = {}

                home_score = 0
                for stat in match['home_time']:
                    if 'points' in stat:
                        time = int(stat['time']) + 1
                        if time <= 48:

                            if time not in point_dict:
                                point_dict[time] = {'home': 0, 'away': 0, 'time': time}

                            point_dict[time]['home'] += stat['points']
                            home_score += stat['points']

                away_score = 0
                for stat in match['away_time']:
                    if 'points' in stat:
                        time = int(stat['time']) + 1
                        if time <= 48:

                            if time not in point_dict:
                                point_dict[time] = {'home': 0, 'away': 0, 'time': time}

                            point_dict[time]['away'] += stat['points']
                            away_score += stat['points']

                # Convert to list to sort by time
                point_list = [v for v in point_dict.values()]
                point_list.sort(key=operator.itemgetter('time'))

                game['home_pts'] = home_score
                game['away_pts'] = away_score
                game['time'] = point_list

                # Append the id to the list so that the match doesn't get selected again
                ids.append(match['_id'])

                data.append(game)

        x += 1

    shuffle(data)
    return pd.DataFrame(data)
