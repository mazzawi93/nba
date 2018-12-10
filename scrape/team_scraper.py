import re, requests, time
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver

from db import mongo
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
    if year > 2019 or year < 1950:
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
    m = mongo.Mongo()

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
        m.insert('game_log', result)


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
    m = mongo.Mongo()

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
    m.update('game_log', {'_id': game_id}, {'$set': {'pbp': pbp}})


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
    m = mongo.Mongo()

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
        season['_id'] = season['team_id'] + '_' + str(season_year)

        # Remove unwanted stats
        to_remove = ['rank_team', 'foo', 'g', 'mp_per_g']
        for k in to_remove:
            season.pop(k, None)

        # Add to MongoDB
        m.insert('team_season', season)

def scrape_betting_page(url = 'https://classic.sportsbookreview.com/betting-odds/nba-basketball/money-line/', sel_browser = None, mongo_driver = None, game_date = None):

    team_names = scrape_utils.team_names()

    full_teams = ['Atlanta', 'Boston', 'Brooklyn', 'Charlotte', 'Chicago',
              'Cleveland', 'Dallas', 'Denver', 'Detroit',
              'Golden State', 'Houston', 'Indiana', 'L.A. Clippers',
              'L.A. Lakers', 'Memphis', 'Miami', 'Milwaukee',
              'Minnesota', 'New Orleans', 'New York', 'Oklahoma City',
              'Orlando', 'Philadelphia', 'Phoenix', 'Portland',
              'Sacramento', 'San Antonio', 'Toronto', 'Utah',
              'Washington']

    if sel_browser is None:
        browser = webdriver.Chrome('chromedriver')
    else:
        browser = sel_browser

    browser.get(url)
    time.sleep(5)

    # Stop the page from loading
    browser.execute_script("window.stop()");

    # Sportsbooks
    sb = browser.find_elements_by_id('bookName')
    sportsbooks = ['Opening']

    # Create list of sportsbooks
    for sportbook in sb:
        if len(sportbook.text) > 1:
            sportsbooks.append(sportbook.text)

    # Get team names and odds
    games = browser.find_elements_by_class_name('eventLine')

    sportsbooks_games = []

    for game in games:
        team_elements = game.find_elements_by_tag_name('a')

        i = 0

        away_team = None
        home_team = None

        # Assign team to correct location
        for team in team_elements:
            if i == 1:
                away_team = team.text
            elif i == 2:
                home_team = team.text
            i += 1

        odds_elements = game.find_elements_by_class_name('eventLine-book-value')

        i = 0
        away_odds = []
        home_odds = []
        home_even = False

        for game_odds in odds_elements:

            if i > 3:

                if i == 4 and game_odds.text == '':
                    home_even = True

                try:
                    odds = int(game_odds.text)

                    # Convert odds to decimal
                    if odds >= 0:
                        odds = round(odds / 100 + 1, 2)
                    else:
                        odds = round(100 / abs(odds) + 1, 2)

                    # Home or away odds
                    if i % 2 == 0:
                        if home_even:
                            try:
                                home_odds.append(odds)
                            except ValueError:
                                home_odds.append(0)
                        else:
                            try:
                                away_odds.append(odds)
                            except ValueError:
                                away_odds.append(0)
                    elif i % 2 != 0:
                        if home_even:
                            try:
                                away_odds.append(odds)
                            except ValueError:
                                away_odds.append(0)
                        else:
                            try:
                                home_odds.append(odds)
                            except ValueError:
                                home_odds.append(0)
                except ValueError:
                    pass

            i += 1
        try:
            home_team = scrape_utils.rename_team(team_names[full_teams.index(home_team)])
            away_team = scrape_utils.rename_team(team_names[full_teams.index(away_team)])



            if mongo_driver is not None:
                sportsbook_odds = {'sportsbooks': [{'sportsbook': sb, 'home_odds':ho, 'away_odds': ao} for sb, ho, ao in zip(sportsbooks, home_odds, away_odds)]}
                query = mongo_driver.update('game_log', {'date': game_date, 'home.team': home_team, 'away.team': away_team}, {'$set': {'odds': sportsbook_odds}})
            else:

                sportsbook_odds = [{'sportsbook': sb, 'home_odds': ho, 'away_odds': ao, 'home_team': home_team, 'away_team': away_team} for sb, ho, ao in zip(sportsbooks, home_odds, away_odds)]
                sportsbooks_games.extend(sportsbook_odds)

        except ValueError:
            pass

    if sel_browser is None:
        browser.close()

    if mongo_driver is None:
        return pd.DataFrame(sportsbooks_games)



def betting_lines(year):
    """
    Add historical betting lines to the database

    :param year: NBA Season
    """

    # MongoDB Collection
    m = mongo.Mongo()

    # Webapges are by dates
    all_dates = m.find('game_log', {'season': year}, {'_id': 0, 'date': 1}).distinct('date')

    browser = webdriver.Chrome('chromedriver')

    # Iterate through each date in a season
    for game_date in all_dates:

        # Get URL
        url = 'https://classic.sportsbookreview.com/betting-odds/nba-basketball/money-line/?date=' + datetime.strftime(game_date, '%Y%m%d')

        scrape_betting_page(url, browser, m, game_date)

    browser.close()
