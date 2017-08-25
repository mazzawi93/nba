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

    # To find opponent statistics
    opponent = re.compile('^opp_.*$')

    # Loop through every game in a team's season
    for game in games.find_all('tr', {'class': None}):

        curr_team = {'team': team}
        opp_team = {}

        # Loop through each stat
        for stat in game.find_all('td'):

            stat_name = stat['data-stat']

            # These are opponent stats
            if re.match(opponent, stat_name):
                opp_team[stat_name[4:]] = scrape_utils.stat_parse(stat_name, stat.string)
            else:
                curr_team[stat_name] = scrape_utils.stat_parse(stat_name, stat.string)

        # Remove unnecessary information
        del curr_team['game_season']
        del curr_team['x']

        # Rename relocated teams
        curr_team['team'] = scrape_utils.rename_team(team)
        opp_team['team'] = scrape_utils.rename_team(opp_team.pop('id'))

        # Use the same ID as basketball reference
        result = {'date': datetime.strptime(curr_team.pop('date_game'), "%Y-%m-%d"),
                  'season': year,
                  'result': scrape_utils.determine_home_win(curr_team['game_location'], curr_team.pop('game_result')),
                  '_id': game.find('a')['href'][-17:-5]}

        # Place the teams in the correct spot depending on who is the home team
        if curr_team.pop('game_location') == 0:
            result['home'] = curr_team
            result['away'] = opp_team
        else:
            result['home'] = opp_team
            result['away'] = curr_team

        # Insert into database
        mongo.insert('game_log', result)


def play_by_play(game_id):
    """
    Analyze the time stamps of a game for all it's statistics

    :param game_id: NBA Game id from MongoDB and Basketball Reference
    """

    # HTML Content
    r = requests.get('https://www.basketball-reference.com/boxscores/pbp/' + game_id + '.html')
    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.find(id='pbp').find_all('tr')

    # MongoDB Collection
    mongo = mongo_utils.MongoDB()

    pbp = {
        'home': [],
        'away': []
    }

    quarter = 0
    pattern = re.compile('^[0-9]{1,3}:[0-9]{2}\.[0-9]{1}$')

    for item in table:

        time = None
        x = 0

        play = {}

        # Iterate through row of stats, each row has 6 columns one half for each team
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
    mongo.update('game_log', {'_id': game_id}, {'$set': {'pbp': pbp}})


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
    mongo = mongo_utils.MongoDB()

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
        mongo.insert('team_season', season)


def betting_lines(year):
    """
    Add historical betting lines to the database

    :param year: NBA Season
    """

    url = "scrape/data/nba_betting_odds_%s.html" % year

    soup = BeautifulSoup(open(url), "html.parser")
    table = soup.find('tbody')

    teams = scrape_utils.team_names()

    # MongoDB Collection
    mongo = mongo_utils.MongoDB()

    # Iterate through each game
    for game in table.find_all('tr'):

        # Date
        date = datetime.strptime(game.find('td', {'class': 's2'}).text, "%d.%m.%Y")

        # Teams
        team = game.find('a')

        # TODO: Get the point spreads
        url = team['href'] + '%ou'

        print(url)

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

        query = {'home.team': scrape_utils.rename_team(teams[hi]), 'away.team': scrape_utils.rename_team(teams[ai]),
                 'date': date}
        print(query)
        update = {'$set': {'bet.home': home, 'bet.away': away}}
        mongo.update('game_log', query, update)