import re
import requests
from bs4 import BeautifulSoup

from db import mongo_utils
from scrape import scrape_utils
from datetime import datetime


def get_starting_lineups(team, year):
    """
    Scrape a team's starting lineup for every game in a season.

    :param team: NBA Team (Team abbreviation)
    :param year: NBA Season
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    # Rename team if relocated
    team = scrape_utils.rename_team(team, year)

    # Starting Lineup URL
    url = "http://www.basketball-reference.com/teams/%s/%s_start.html" % (team, year)

    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "html.parser")

    team = scrape_utils.rename_team(team)

    # Line up table
    lineup_table = soup.find(id='starting_lineups').find('tbody')

    # Iterate through each game
    for game in lineup_table.find_all('tr', {'class': None}):

        # Information to query mongodb to update collection
        date = game.find('td', {'data-stat': 'date_game'}).text
        date = datetime.strptime(date, '%a, %b %d, %Y')
        opponent = game.find('td', {'data-stat': 'opp_name'})
        opponent = opponent.find('a')['href'][7:10]

        # Determine home team for query
        location = game.find('td', {'data-stat': 'game_location'}).text

        lineup = []

        if location == '@':
            home = opponent
            away = team
            key = 'starters.away'
        else:
            home = team
            away = opponent
            key = 'starters.home'

        # Get the starting lineup
        starters = game.find('td', {'data-stat': 'game_starters'})
        for player in starters.find_all('a'):
            lineup.append(player['href'].rsplit('/', 1)[-1].rsplit('.', 1)[0])

        # Update document
        mongo.update('game_log', {'date': date, 'home.team': home, 'away.team': away}, {'$set': {key: lineup}})


def player_per_game(player):
    """ Scrape a player's yearly per game stats"""

    # Mongo
    mongo = mongo_utils.MongoDB()

    # Request
    url = "http://www.basketball-reference.com" + player['url']
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
                season[stat['data-stat']] = scrape_utils.stat_parse(stat['data-stat'], stat.string)

            for key in entries:
                if key in season:
                    player_stats[season_year][key] = season.pop(key)

            player_stats[season_year]['per_g'] = season

    mongo.insert('player_per_game', player_stats)


def player_box_score(game_id):
    """
    Scrape all player stats from a specific game and store in Mongo

    :param game_id: MongoDB and Basketball Reference game id
    """

    # HTML Content
    r = requests.get('https://www.basketball-reference.com/boxscores/' + game_id + '.html')
    soup = BeautifulSoup(r.content, "html.parser")

    # MongoDB Collection
    mongo = mongo_utils.MongoDB()

    # The ids of the tables have team names in them
    table_id = re.compile('^box_[a-z]{3}_basic$')

    box_score = {
        'home': {},
        'away': {}
    }

    team = 'away'

    for table in soup.find_all(id=table_id):
        sub_table = table.find('tbody')

        for player in sub_table.find_all('tr', {'class': None}):

            player_stats = {}

            # Player ID
            player_id = player.find('th')
            player_id = player_id['data-append-csv']

            # Loop through each stat
            for stat in player.find_all('td'):
                player_stats[stat['data-stat']] = scrape_utils.stat_parse(stat['data-stat'], stat.string)

            # If this key exists it means the player did not play
            if 'reason' not in player_stats:
                box_score[team][player_id] = player_stats

        team = 'home'

    # Insert into database
    mongo.update('game_log', {'_id': game_id}, {'$set': {'players': box_score}})
