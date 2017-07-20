from datetime import timedelta
from pymongo import MongoClient
from db import process_utils
import pandas as pd


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
    season = process_utils.season_check(season)

    # Check team values
    team = process_utils.team_check(team)

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


def games_in_last_5(col, team, date):
    """
    Determine the amount of games a team has played in the last 5 days
    :param col: MongoDB Collection
    :param team: NBA Team
    :param date: Date of the game
    :return: Number of games played in the last 5 days
    """

    # MongoDB Queries
    team_search = [{'home.team': team}, {'away.team': team}]
    date_search = {'$lt': date, '$gte': date - timedelta(days=5)}

    return col.find({'$or': team_search, 'date': date_search}).count()


def rest_games(col, team, date, season):
    """
    Determine the amount of days off before a team's next game  
    :param col: MongoDB collection
    :param team: NBA Team
    :param date: Date of their game
    :param season: NBA Season
    :return: Amount of rest days
    
    """

    # MongoDB Queries
    team_search = [{'home.team': team}, {'away.team': team}]
    date_search = {'$lt': date}

    # Find the last game played
    rest_game = col.find({"$or": team_search, "date": date_search, 'season': season}).sort('date', -1).limit(1)

    # Return rest days or None if it's the first game of the season
    if rest_game.count(with_limit_and_skip=True) == 0:
        return None
    else:
        for game in rest_game:
            rest = date - game['date']
            return rest.days


def last_10(col, team, date, season):
    """
    Average the team's statistics over the last 10 games
    :param col: MongoDB collection
    :param team: NBA Team
    :param date: Game's Date
    :param season: Game's Season
    :return: A Dictionary of team stats averaged out over the number of games
    """

    # MongoDB Queries
    team_search = [{'home.team': team}, {'away.team': team}]
    date_search = {'$lt': date}

    # Last 10 games
    games = col.find({'$or': team_search, 'date': date_search, 'season': season}).limit(10)

    # The beginning of the season will have less than 10 games
    num = (games.count(with_limit_and_skip=True))

    # Dict of last games' statistics
    last = {}

    # If there are less than 5 games then return None
    if num > 4:
        for game in games:

            if game['home']['team'] == team:
                stats = game['home']
            else:
                stats = game['away']

            # Remove team name from stats
            del stats['team']

            # Accumulate the stats
            for key in stats:
                if key in last:
                    last[key] = float(last[key]) + float(stats[key])
                else:
                    last[key] = float(stats[key])

        # Divide by the number of games
        for key in last:
            last[key] = last[key] / num

        return last
    else:
        return {}


def recent_meetings(col, home_team, away_team, date, season):
    """
    Determine the status of recent meetings between two teams
    Victory is defined as 1 or -1, so the score is calculated by result/(current_season-history_season+1)
    :param col: MongoDB Collection
    :param home_team: Home Team
    :param away_team: Away Team
    :param date: Date of the game
    :param season: Season of the game
    :return: Sum of the score sum(result/(current_season-history_season+1))
    """

    # MongoDB Queries
    home_search = [{'home.team': home_team}, {'away.team': home_team}]
    away_search = [{'home.team': away_team}, {'away.team': away_team}]

    # Find the last games between the two teams
    matchups = col.find({'$and': [{'$or': home_search}, {'$or': away_search}],
                         'date': {'$lt': date}}).limit(12)

    score = 0

    for game in matchups:

        result = game['result'] / (season - game['season'] + 1)

        # The home team winning always has a value of 1, thus if the home team defined is playing
        # away, the score must be subtracted
        if game['home']['team'] == home_team:
            score += result
        else:
            score -= result

    return score
