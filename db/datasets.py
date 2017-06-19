import operator
import string
from random import shuffle
import pandas as pd
from pymongo import MongoClient

from db import game_log
from db import process_utils


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
    season = process_utils.season_check(season)

    # Check team values
    team = process_utils.team_check(team)

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
                    match = game_log.select_match(margin, ids)
                else:
                    game['home'] = teams[i]
                    game['away'] = team
                    match = game_log.select_match(-margin, ids)

                # Iterate through point times
                point_times = []

                home_score = 0
                for stat in match['home_time']:
                    if 'points' in stat:
                        if stat['time'] <= 48:
                            stat['time'] = round(stat['time'] / 48, 4)
                            stat['home'] = 1
                            home_score += stat['points']
                            point_times.append(stat)

                away_score = 0
                for stat in match['away_time']:
                    if 'points' in stat:
                        if stat['time'] <= 48:
                            stat['time'] = round(stat['time'] / 48, 4)
                            stat['home'] = 0
                            away_score += stat['points']
                            point_times.append(stat)

                # Sort the points based on time
                point_times.sort(key=operator.itemgetter('time'))

                game['home_pts'] = home_score
                game['away_pts'] = away_score
                game['time'] = point_times

                # Append the id to the list so that the match doesn't get selected again
                ids.append(match['_id'])

                data.append(game)

        x += 1

    shuffle(data)
    return pd.DataFrame(data)


def process_time(times_list, stat, home):
    # Don't do overtime for now
    if stat['time'] <= 48:
        stat['time'] = round(stat['time'] / 48, 4)

        if home is True:
            stat['home'] = 1
        else:
            stat['home'] = 0

        times_list.append(stat)
