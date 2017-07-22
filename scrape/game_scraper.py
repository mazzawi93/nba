from datetime import datetime

import re
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

from db import mongo_utils
from scrape import scrape_utils

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

    # Get HTML content
    url = 'http://www.basketball-reference.com/teams/%s/%s/gamelog' % (team, year)
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")
    season_stats = soup.find(id='tgl_basic')
    games = season_stats.find('tbody')

    # MongoDB Collection
    mongo = mongo_utils.MongoDB()

    # Loop through every game in a team's season
    for game in games.find_all('tr', {'class': None}):

        stats = {}

        # Loop through each stat
        for stat in game.find_all('td'):
            stats[stat['data-stat']] = stat.string

        # Rename relocated teams
        team = scrape_utils.rename_team(team)
        stats['opp_id'] = scrape_utils.rename_team(stats['opp_id'])

        # Separate the two teams' stats to keep them consistent for Mongo
        team1 = {
            'team': team,
            'pts': int(stats['pts']),
            'fg': int(stats['fg']),
            'fga': int(stats['fga']),
            'fg_pct': float(stats['fg_pct']),
            'fg3': int(stats['fg3']),
            'fg3a': int(stats['fg3a']),
            'fg3_pct': float(stats['fg3_pct']),
            'ft': int(stats['ft']),
            'fta': int(stats['fta']),
            'ft_pct': float(stats['ft_pct']),
            'orb': int(stats['orb']),
            'trb': int(stats['trb']),
            'ast': int(stats['ast']),
            'stl': int(stats['stl']),
            'blk': int(stats['blk']),
            'tov': int(stats['tov']),
            'pf': int(stats['pf'])
        }

        team2 = {
            'team': stats['opp_id'],
            'pts': int(stats['opp_pts']),
            'fg': int(stats['opp_fg']),
            'fga': int(stats['opp_fga']),
            'fg_pct': float(stats['opp_fg_pct']),
            'fg3': int(stats['opp_fg3']),
            'fg3a': int(stats['opp_fg3a']),
            'fg3_pct': float(stats['opp_fg3_pct']),
            'ft': int(stats['opp_ft']),
            'fta': int(stats['opp_fta']),
            'ft_pct': float(stats['opp_ft_pct']),
            'orb': int(stats['opp_orb']),
            'trb': int(stats['opp_trb']),
            'ast': int(stats['opp_ast']),
            'stl': int(stats['opp_stl']),
            'blk': int(stats['opp_blk']),
            'tov': int(stats['opp_tov']),
            'pf': int(stats['opp_pf'])
        }

        result = {'date': datetime.strptime(stats['date_game'], "%Y-%m-%d"),
                  'season': year,
                  'result': scrape_utils.determine_home_win(stats['game_location'], stats['game_result'])}

        # Place the teams in the correct spot depending on who is the home team
        if stats['game_location'] is None:
            result['home'] = team1
            result['away'] = team2
        else:
            result['home'] = team2
            result['away'] = team1

        # Unique ID is home+away+date
        result['_id'] = result['home']['team'] + result['away']['team'] + result['date'].strftime('%d%m%Y')

        # Insert into database
        mongo.insert('game_log', result)

        # URL segment for more in depth game stats
        box_score = game.find('a')

        # bs_url = 'http://www.basketball-reference.com/boxscores' + box_score['href'][-18:]
        pbp_url = 'http://www.basketball-reference.com/boxscores/pbp' + box_score['href'][-18:]
        play_by_play(mongo, pbp_url, result['_id'])


def play_by_play(mongo, url, game_id):
    """
    Analyze the time stamps of a game for all it's statistics

    :param game_id: MongoDB id corresponsing to game log
    :param mongo: Custom MongoDB class
    :param url: The URL of the game for the play by play
    """

    # HTML Content
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.find(id='pbp').find_all('tr')

    pbp = {
        '_id': game_id,
        'home': [],
        'away': [],
    }

    quarter = 0
    for item in table:
        time = None

        x = 0

        pattern = re.compile('^[0-9]{1,3}:[0-9]{2}\.[0-9]{1}$')

        play = {}
        for stat in item.find_all('td'):

            x += 1

            check = True

            # A player scored
            if "makes" in stat.text:
                scrape_utils.field_goal_update(stat.find('a')['href'], stat.text, play, True)
            # Player missed a shot
            elif "misses" in stat.text:
                scrape_utils.field_goal_update(stat.find('a')['href'], stat.text, play, False)
            # Account for other basketball stats
            elif "Defensive rebound" in stat.text:
                if 'Team' not in stat.text:
                    play['drb'] = 1
            elif "Offensive rebound" in stat.text:
                if 'Team' not in stat.text:
                    play['orb'] = 1
            elif "Turnover" in stat.text:
                play['turnover'] = 1
            elif "foul" in stat.text:
                play['foul'] = 1
            elif "timeout" in stat.text:
                play['timeout'] = 1
            elif "enters" in stat.text:
                play['sub'] = 1
            else:
                check = False

            # Determine if home or away
            if check is True:
                if x == 2:
                    play['home'] = 0
                elif x == 6:
                    play['home'] = 1

            # Different quarters including multiple overtimes
            if pattern.match(stat.text):
                time = scrape_utils.play_time(quarter, stat.text[:-2])

        if play:
            play['time'] = time

            if play['home'] == 1:
                del play['home']
                pbp['home'].append(play)
            else:
                del play['home']
                pbp['away'].append(play)

        # Going to next quarter
        if time is None:
            quarter += 1

    # Insert into database
    mongo.insert('play_by_play', pbp)


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


def scrape_all(start_year, end_year):
    """
    Iterate through each team and year to get season game logs and yearly stats
    """
    teams = scrape_utils.team_names()

    for team in teams:
        team_season_stats(team)
        for year in range(start_year, end_year + 1):
            print("%s (%s)" % (team, year))
            season_game_logs(team, year)
