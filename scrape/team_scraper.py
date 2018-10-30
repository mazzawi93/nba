from datetime import datetime, timedelta

import re, requests, time, pytz
from bs4 import BeautifulSoup
from db import mongo
from scrape import scrape_utils
import pandas as pd

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


def betting_lines(year):
    """
    Add historical betting lines to the database

    :param year: NBA Season
    """

    teams = scrape_utils.team_names()

    # MongoDB Collection
    m = mongo.Mongo()

    # Webdrivers
    browser = scrape_utils.oddsportal_login()
    game_browser = scrape_utils.oddsportal_login()

    scrape = True
    current_page = 1
    final_href = ''

    while scrape:

        if year == 2019:
            url = 'https://www.oddsportal.com/basketball/usa/nba/results/#/page/' + str(current_page) +'/'
        else:
            url = 'https://www.oddsportal.com/basketball/usa/nba-' + str(year - 1) + '-' + str(year) + '/results/#/page/' + str(current_page) +'/'

        if url == final_href:
            scrape = False

        browser.get(url)

        time.sleep(5)

        # This will skip a page of playoff games
        if current_page > 1 or year == 2019:
            table = browser.find_element_by_xpath('//tbody')
            date = None
            for row in table.find_elements_by_xpath('.//tr'):

                # Get Row class
                c = row.get_attribute('class')
                try:
                    # Date
                    if c == 'center nob-border' and row.text != '':
                        date = row.text[0:11]
                    elif re.search('deactivate', c) and row.text != '':

                        # Get all Game Odds
                        href = row.find_element_by_xpath('.//a').get_attribute('href')
                        sportsbook_odds = scrape_game_odds(game_browser, href)

                        i = 1
                        # Iterate through row elements to get game information to match with local database
                        for ele in row.find_elements_by_xpath('.//td'):

                            if i == 1:
                                timestamp = ele.text
                            if i == 2:

                                game_teams = ele.text.replace('\n ', '').split(' - ')
                                home_team = teams[full_teams.index(game_teams[0])]
                                away_team = teams[full_teams.index(game_teams[1])]

                            i = i + 1

                        date2 = datetime.strptime(date + ' ' + timestamp, '%d %b %Y %H:%M')

                        # Convert to the correct time zone
                        gmt = pytz.timezone('Etc/GMT+0')
                        local = pytz.timezone('America/New_York')
                        gmt_dt = gmt.localize(date2)
                        local_dt = gmt_dt.astimezone(local)
                        local_dt = datetime(local_dt.year, local_dt.month, local_dt.day)

                        # Rename team abr. if needed
                        home_team = scrape_utils.rename_team(home_team)
                        away_team = scrape_utils.rename_team(away_team)



                        # Update the database with odds
                        query = m.update('game_log', {'date': local_dt, 'home.team': home_team, 'away.team': away_team}, {'$set': {'odds': sportsbook_odds}})


                        # IF the game doesn't exist, subtract the date by one and try again (For some reason the dates are messed on the odds website)
                        if query['updatedExisting'] == False:
                            query = m.update('game_log', {'date': local_dt-timedelta(days = 1), 'home.team': home_team, 'away.team': away_team}, {'$set': {'odds': sportsbook_odds}})

                        print(home_team, away_team, local_dt, query)

                except ValueError:
                    pass
                except TypeError:
                    pass

        # If this is the first page, find the last page url
        if current_page == 1:
            page = browser.find_element_by_id('pagination')
            for anchor in page.find_elements_by_xpath('.//a'):
                final_href = anchor.get_attribute('href')

        current_page = current_page + 1

    browser.quit()
    game_browser.quit()


def scrape_game_odds(selenium_driver, url):
    """
    Scrape odds by all sportsbooks for a specific game and return a DataFrame.

    :param selenium_driver: Driver that is already logged into oddsportal
    :param url: Url of game with all betting odds

    """

    # Go to Game URL
    selenium_driver.get(url)

    time.sleep(5)

    # Table with all the odds
    odds_table = selenium_driver.find_element_by_xpath('//*[@id="odds-data-table"]/div[1]/table/tbody')

    sportsbooks = []

    # Iterate through each row of the table and then get the elements for sportsbook/odds
    for sportsbook_row in odds_table.find_elements_by_xpath('.//tr'):

        i = 1
        for sportsbook_stat in sportsbook_row.find_elements_by_xpath('.//td'):

            # Table rows are in the same format
            if i == 1:
                sportsbook = sportsbook_stat.text
            elif i == 2:
                home_odds = float(sportsbook_stat.text)
            elif i == 3:
                away_odds = float(sportsbook_stat.text)
            i += 1

        sportsbooks.append({'sportsbook': sportsbook.strip(), 'home_odds': home_odds, 'away_odds': away_odds})

    # TODO: Remove duplicate rows
    sportsbooks = {'sportsbooks': sportsbooks}

    return sportsbooks
