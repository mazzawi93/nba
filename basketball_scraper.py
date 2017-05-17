import re
from bs4 import BeautifulSoup
import requests
import string
from datetime import datetime
from pymongo import MongoClient


def team_names():
    """
    Scrape all team names of the NBA
    
    :return: list of NBA Teams
    """

    # Url for all teams in the NBA
    url = 'http://www.basketball-reference.com/teams/'

    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    # Page also lists defunct franchises, only want currently active teams
    active_teams = soup.find(id="teams_active")

    teams = []

    # Iterate through teams to get the team abbreviation (ex. TOR)
    for active_team in active_teams.find_all('tr', {'class': "full_table"}):
        team_url = active_team.find('a')
        team_name = team_url['href']
        teams.append(team_name[7:10])

    return teams


def season_game_logs(team, year):
    """
    Scrape Basketball-Reference for every game log in a given team's season and store it in MongoDB.
    
    :param team: Team to scrape
    :param year: Season in year
    :raise ValueError: If year exceeds NBA season ranges
    
    """

    if year > 2017 or year < 1950:
        raise ValueError('Year Value Incorrect')

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    # Renaming Teams in Recent years (Basketball-Reference has different urls for the same team in different years)
    if team == 'NJN' and year > 2012:
        team = 'BRK'
    elif team == 'CHA' and year > 2014:
        team = 'CHO'
    elif team == 'NOH' and year > 2013:
        team = 'NOP'

    url = "http://www.basketball-reference.com/teams/%s/%s/gamelog" % (team, year)

    # The incorrect team won't return 404, but a page with no statistics
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    season_stats = soup.find(id='tgl_basic')

    try:
        games = season_stats.find('tbody')

        # Loop through every game in a team's season
        for game in games.find_all('tr', {'class': None}):

            match = {}

            # Loop through each stat
            for stat in game.find_all('td'):
                match[stat['data-stat']] = stat.string

            # Rename relocated teams
            team = rename_team(team)
            match['opp_id'] = rename_team(match['opp_id'])

            # Separate the two teams' stats to keep them consistent for Mongo
            team1 = {
                'team': team,
                'pts': match['pts'],
                'fg': match['fg'],
                'fga': match['fga'],
                'fg_pct': match['fg_pct'],
                'fg3': match['fg3'],
                'fg3a': match['fg3a'],
                'fg3_pct': match['fg3_pct'],
                'ft': match['ft'],
                'fta': match['fta'],
                'ft_pct': match['ft_pct'],
                'orb': match['orb'],
                'trb': match['trb'],
                'ast': match['ast'],
                'stl': match['stl'],
                'blk': match['blk'],
                'tov': match['tov'],
                'pf': match['pf']
            }

            team2 = {
                'team': match['opp_id'],
                'pts': match['opp_pts'],
                'fg': match['opp_fg'],
                'fga': match['opp_fga'],
                'fg_pct': match['opp_fg_pct'],
                'fg3': match['opp_fg3'],
                'fg3a': match['opp_fg3a'],
                'fg3_pct': match['opp_fg3_pct'],
                'ft': match['opp_ft'],
                'fta': match['opp_fta'],
                'ft_pct': match['opp_ft_pct'],
                'orb': match['opp_orb'],
                'trb': match['opp_trb'],
                'ast': match['opp_ast'],
                'stl': match['opp_stl'],
                'blk': match['opp_blk'],
                'tov': match['opp_tov'],
                'pf': match['opp_pf']
            }

            result = {'date': datetime.strptime(match['date_game'], "%Y-%m-%d"),
                      'season': year}

            # Place the teams in the correct spot depending on who is the home team
            if match['game_location'] is None:
                result['home'] = team1
                result['away'] = team2
            else:
                result['home'] = team2
                result['away'] = team1

            # Store match result
            result['result'] = determine_home_win(match['game_location'], match['game_result'])

            # Store result in MongoDB if the game doesn't already exist
            if collection.find_one(result) is None:
                collection.insert_one(result)

    except AttributeError:
        print("%s doesn't exist" % team)

    client.close()


def store_team_data(years):
    teams = team_names()

    for team in teams:
        print("Team: %s" % team)
        team_season_stats(team)
        for x in range(2018 - years, 2018):
            print("Season: %s" % x)
            season_game_logs(team, x)


def team_season_stats(team):
    url = 'http://www.basketball-reference.com/teams/%s/stats_per_game_totals.html' % team

    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    client = MongoClient()
    db = client.basketball
    collection = db.team_season

    season_stats = soup.find(id='stats').find('tbody')

    for year in season_stats.find_all('tr', {'class': None}):

        season_year = year.find('th').text[0:4]
        season_year = int(season_year) + 1
        season = {
            'year': season_year
        }

        # Loop through each stat
        for stat in year.find_all('td'):
            season[stat['data-stat']] = stat.string

        season['team_id'] = rename_team(season['team_id'])

        del season['rank_team']
        del season['foo']
        del season['g']
        del season['mp_per_g']

        if collection.find_one(season) is None:
            collection.insert_one(season)

    client.close()


def get_starting_lineups(team, year):
    """ Add team's starting lineup to game in Mongo database"""

    url = "http://www.basketball-reference.com/teams/%s/%s_start.html" % (team, year)

    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "html.parser")

    lineups = soup.find(id='starting_lineups').find('tbody')

    # Iterate through each game to find the starting lineup
    for game in lineups.find_all('tr', {'class': None}):

        lineup = []

        # TODO: Convert Date to the same format as games are stored (01-21-17)
        date = game.find('td', {'data-stat': 'date_game'}).text

        # Get the starting lineup
        starters = game.find('td', {'data-stat': 'game_starters'})
        for player in starters.find_all('a'):
            lineup.append(player.text)

            # TODO: Append this data to a game stored in the Mongo Database

        print(date)
        print(lineup)


def get_active_players():
    """ Get a list of all active NBA players (name and url to stats page) """

    active_players = []

    # Iterate through each letter of the alphabet
    for letter in string.ascii_lowercase:
        url = "http://www.basketball-reference.com/players/%s/" % letter
        r = requests.get(url)
        soup = BeautifulSoup(r.content, "html.parser")

        # Not every letter is represented by a player
        try:

            # Player table
            player_table = soup.find(id='players').find('tbody')

            # Iterate through each player, active players have a <strong> tag
            for player in player_table.find_all('tr'):

                active = player.find('strong')

                if active is not None:
                    player_info = {
                        'name': active.text,
                        'url': active.find('a')['href']
                    }

                    active_players.append(player_info)

        except Exception as e:
            print(e)

    return active_players


def get_player_stats(player):
    """ Scrape a player's yearly stats"""

    # TODO: Add a player's advanced stats, right now it is only per game

    url = "http://www.basketball-reference.com" + player['url']

    # Request
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    # Player's statistics
    per_game = soup.find(id="per_game").find('tbody')

    # When there are missing years, there is no id or data-stat for the year
    regex = re.compile('.*')

    # Player dictionary
    player_stats = {
        '_id': url.rsplit('/', 1)[-1].rsplit('.', 1)[0],
        'name': player['name']
    }

    # These entries are defined in the per game and advanced tables
    # Only want them to be displayed once per season for a player
    entries = ['age', 'team_id', 'lg_id', 'pos', 'g', 'gs', 'mp']

    # Iterate through the years
    for year in per_game.find_all('tr', {'id': regex}):

        # Season stats
        season = {}

        season_year = year['id'][9:13]

        # If a player is traded midway through the season, the year's totals for
        # both teams is the first row.  Right now only the totals are stored
        if season_year not in player_stats:
            player_stats[season_year] = {}

            # Each stat in a season (Per Game)
            for stat in year.find_all('td', {'data-stat': regex}):
                season[stat['data-stat']] = stat.string

            for key in entries:
                if key in season:
                    player_stats[season_year][key] = season[key]
                    del season[key]

            player_stats[season_year]['per_g'] = season

    return player_stats


def determine_home_win(location, result):
    """
    Determine the result of the home team given the location and result for a a specific team
    
    :param location: Location of the game (None for Home, @ for Away)
    :param result: Result of the game (W for Win, L for Loss)
    :return: 1 or -1 for the home result
    :raises Value Error: If result is not W or L, and if location is not None or @
    
    """

    if result != 'W' and result != 'L':
        raise ValueError('The game result is incorrect, must be W or L')

    if location is not None and location != '@':
        raise ValueError('Location is incorrectly entered')

    # Determine Home Winner
    if location is None:
        if result == 'W':
            return 1
        else:
            return -1
    else:
        if result == 'L':
            return 1
        else:
            return -1


def rename_team(team):
    """
    Rename a team that has relocated to keep the database consistent
    
    :param team: Team Abbreviation to be named
    :return: Changed team name if the team has relocated, otherwise the same name is returned
         
    """

    # Rename relocated team to current abbreviation
    if team == 'NJN':
        team = 'BRK'
    elif team == 'CHA':
        team = 'CHO'
    elif team == 'NOH':
        team = 'NOP'

    return team


store_team_data(6)

