from datetime import timedelta


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
