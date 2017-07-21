import string
import re
import requests
from bs4 import BeautifulSoup


def get_starting_lineups(team, year):
    """
    Scrape a team's starting lineup for every game in a season.

    :param team: NBA Team (Team abbreviation)
    :param year: NBA Season
    :return: Dict containing date and starting lineup
    """

    # Starting Lineup URL
    url = "http://www.basketball-reference.com/teams/%s/%s_start.html" % (team, year)

    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "html.parser")

    # Line up table
    lineup_table = soup.find(id='starting_lineups').find('tbody')

    lineups = []

    # Iterate through each game
    for game in lineup_table.find_all('tr', {'class': None}):

        # TODO: Convert Date datetime to be able to query mongodb
        date = game.find('td', {'data-stat': 'date_game'}).text

        lineup = {
            'date': date,
            'starters': []
        }

        # Get the starting lineup
        starters = game.find('td', {'data-stat': 'game_starters'})
        for player in starters.find_all('a'):
            lineup['starters'].append(player.text)

        lineups.append(lineup)

    return lineups


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

    # TODO: Add a player's advanced stats, right now it is only basic stats per game

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
