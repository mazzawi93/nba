from datetime import datetime
from scrape import scrape_utils
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL',
         'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR',
         'UTA', 'WAS']

full_teams = ['Atlanta Hawks', 'Boston Celtics', 'Brooklyn Nets', 'Charlotte Hornets', 'Chicago Bulls',
              'Cleveland Cavaliers', 'Dallas Mavericks', 'Denver Nuggets', 'Detroit Pistons',
              'Golden State Warriors', 'Houston Rockets', 'Indiana Pacers', 'Los Angeles Clippers',
              'Los Angeles Lakers', 'Memphis Grizzlies', 'Miami Heat', 'Milwaukee Bucks',
              'Minnesota Timberwolves', 'New Orleans Pelicans', 'New York Knicks', 'Oklahoma City Thunder',
              'Orlando Magic', 'Philadelphia 76ers', 'Phoenix Suns', 'Portland Trail Blazers',
              'Sacramento Kings', 'San Antonio Spurs', 'Toronto Raptors', 'Utah Jazz',
              'Washington Wizards']


def season_game_logs(team, year):
    """
    Scrape Basketball-Reference for every game log in a given team's season and store it in MongoDB.

    :param team: Team to scrape
    :param year: Season in year
    :raise ValueError: If year exceeds NBA season ranges

    """

    # Check year value
    if year > 2017 or year < 1950:
        raise ValueError('Year Value Incorrect')

    # Rename teams that moved
    team = scrape_utils.rename_team(team, year)

    # Basketball reference url
    url = 'http://www.basketball-reference.com/teams/%s/%s/gamelog' % (team, year)

    # The incorrect team won't return 404, but a page with no statistics
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    season_stats = soup.find(id='tgl_basic')

    try:

        # MongoDB Collection
        client = MongoClient()
        db = client.basketball
        collection = db.game_log

        # Games table on HTML
        games = season_stats.find('tbody')

        # Loop through every game in a team's season
        for game in games.find_all('tr', {'class': None}):

            match = {}

            # Loop through each stat
            for stat in game.find_all('td'):
                match[stat['data-stat']] = stat.string

            # Rename relocated teams
            team = scrape_utils.rename_team(team)
            match['opp_id'] = scrape_utils.rename_team(match['opp_id'])

            # Separate the two teams' stats to keep them consistent for Mongo
            team1 = {
                'team': team,
                'pts': int(match['pts']),
                'fg': int(match['fg']),
                'fga': int(match['fga']),
                'fg_pct': float(match['fg_pct']),
                'fg3': int(match['fg3']),
                'fg3a': int(match['fg3a']),
                'fg3_pct': float(match['fg3_pct']),
                'ft': int(match['ft']),
                'fta': int(match['fta']),
                'ft_pct': float(match['ft_pct']),
                'orb': int(match['orb']),
                'trb': int(match['trb']),
                'ast': int(match['ast']),
                'stl': int(match['stl']),
                'blk': int(match['blk']),
                'tov': int(match['tov']),
                'pf': int(match['pf'])
            }

            team2 = {
                'team': match['opp_id'],
                'pts': int(match['opp_pts']),
                'fg': int(match['opp_fg']),
                'fga': int(match['opp_fga']),
                'fg_pct': float(match['opp_fg_pct']),
                'fg3': int(match['opp_fg3']),
                'fg3a': int(match['opp_fg3a']),
                'fg3_pct': float(match['opp_fg3_pct']),
                'ft': int(match['opp_ft']),
                'fta': int(match['opp_fta']),
                'ft_pct': float(match['opp_ft_pct']),
                'orb': int(match['opp_orb']),
                'trb': int(match['opp_trb']),
                'ast': int(match['opp_ast']),
                'stl': int(match['opp_stl']),
                'blk': int(match['opp_blk']),
                'tov': int(match['opp_tov']),
                'pf': int(match['opp_pf'])
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
            result['result'] = scrape_utils.determine_home_win(match['game_location'], match['game_result'])

            # If game is not in DB, then scrape time stamps for all stats and store
            if collection.find_one(
                    {'home.team': result['home'], 'away.team': result['away'], 'date': result['date']}) is None:
                # Find the URL for a game's play by play stat for the time for each stat
                pbp = game.find('a')
                pbp_url = 'http://www.basketball-reference.com/boxscores/pbp' + pbp['href'][-18:]
                pbp_stats = scrape_utils.stat_distribution(pbp_url)

                result['home_time'] = pbp_stats['home'],
                result['away_time'] = pbp_stats['away']

                collection.insert_one(result)
    except AttributeError:
        print("%s doesn't exist" % team)


def team_season_stats(team):
    """
    Scrape a team's season stats for every year and store it in the database
    :param team: NBA Team
    """

    # Get HTML Content
    url = 'http://www.basketball-reference.com/teams/%s/stats_per_game_totals.html' % team
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    # MongoDB Collection
    client = MongoClient()
    db = client.basketball
    collection = db.team_season

    # Team's yearly stats are displayed in a table
    season_stats = soup.find(id='stats').find('tbody')

    # Iterate through each year
    for year in season_stats.find_all('tr', {'class': None}):

        season_year = year.find('th').text[0:4]
        season_year = int(season_year) + 1
        season = {'year': season_year}

        # Loop through each stat
        for stat in year.find_all('td'):
            season[stat['data-stat']] = stat.string

        # Rename relocated teams
        season['team_id'] = scrape_utils.rename_team(season['team_id'])

        # Remove unwanted stats
        to_remove = ['rank_team', 'foo', 'g', 'mp_per_g']
        for k in to_remove:
            season.pop(k, None)

        # Add to MongoDB
        if collection.find_one(season) is None:
            collection.insert_one(season)


def betting_lines(year):
    """
    Add historical betting lines to the database

    :param year: NBA Season
    """

    url = "scrape/data/nba_betting_odds_%s.html" % year

    soup = BeautifulSoup(open(url), "html.parser")
    table = soup.find('tbody')

    # MongoDB Collection
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    # Iterate through each game
    for game in table.find_all('tr'):

        # Date
        date = datetime.strptime(game.find('td', {'class': 's2'}).text, "%d.%m.%Y")

        # Teams
        team = game.find('a')

        # TODO: Get the point spreads
        url = team['href']

        # Team indexes in 3-letter code list
        team = team.text.split('-')
        hi = full_teams.index(team[0][:-1])
        ai = full_teams.index(team[1][1:])

        home, away = 0, 0

        # Moneylines
        i = 0
        for bet in game.find_all('td', {'class': 's1'}):
            if i == 0:
                home = round(float(bet.text), 2)
            else:
                away = round(float(bet.text), 2)
            i += 1

        # Add the betting line to the database
        collection.update({'home.team': team[hi], 'away.team': team[ai], 'date': date},
                          {'$set': {'bet.home': home, 'bet.away': away}})


def scrape_all(self):
    """
    Iterate through each team and year to get season game logs and yearly stats
    """

    for team in self.teams:
        self.team_season_stats(team)
        for year in self.years:
            print("%s (%s)" % (team, year))
            self.season_game_logs(team, year)
