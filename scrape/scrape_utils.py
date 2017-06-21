from datetime import datetime

import re
import requests
from bs4 import BeautifulSoup


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


def rename_team(team, year=None):
    """
    Rename a team that has relocated to keep the database consistent

    :param year: NBA Season
    :param team: Team Abbreviation to be named
    :return: Changed team name if the team has relocated, otherwise the same name is returned

    """

    # Rename relocated team to current abbreviation
    if team == 'NJN':
        if year is None or year > 2012:
            team = 'BRK'
    elif team == 'CHA':
        if year is None or year > 2014:
            team = 'CHO'
    elif team == 'NOH':
        if year is None or year > 2013:
            team = 'NOP'

    return team


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


def stat_distribution(url):
    """
    Analyze the time stamps of a game for all it's statistics
    :param url: The URL of the game for the time stamps
    :return: Dict containing time of each stat in a game
    """

    # Request
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    # Play by play table
    table = soup.find(id='pbp').find_all('tr')

    stat_dist = {
        'home': [],
        'away': [],
    }

    quarter = 0
    for item in table:
        time = None

        x = 0

        pattern = re.compile('^[0-9]{1,3}:[0-9]{2}\.[0-9]{1}$')

        score = {}
        for stat in item.find_all('td'):

            x += 1

            check = True

            if "makes" in stat.text:

                player = (stat.find('a')['href'])
                player = player.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                score['player'] = player

                if 'assist' in stat.text:
                    score['assist'] = 1

                if '3-pt' in stat.text:
                    score['points'] = 3
                    score['fgm'] = 1
                    score['fg3m'] = 1
                    score['fga'] = 1
                elif '2-pt' in stat.text:
                    score['points'] = 2
                    score['fgm'] = 1
                    score['fga'] = 1
                elif 'free' in stat.text:
                    score['points'] = 1
                    score['ftm'] = 1
                    score['fta'] = 1
            elif "misses" in stat.text:

                player = (stat.find('a')['href'])
                player = player.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                score['player'] = player

                if '3-pt' in stat.text:
                    score['fga'] = 1
                    score['fg3a'] = 1
                elif '2-pt' in stat.text:
                    score['fga'] = 1
                elif 'free' in stat.text:
                    score['fta'] = 1
            elif "Defensive rebound" in stat.text:
                if 'Team' not in stat.text:
                    score['drb'] = 1
            elif "Offensive rebound" in stat.text:
                if 'Team' not in stat.text:
                    score['orb'] = 1
            elif "Turnover" in stat.text:
                score['turnover'] = 1
            elif "foul" in stat.text:
                score['foul'] = 1
            elif "timeout" in stat.text:
                score['timeout'] = 1
            elif "enters" in stat.text:
                score['sub'] = 1
            else:
                check = False

            if score:

                if check is True:
                    if x == 2:
                        score['home'] = 0
                    elif x == 6:
                        score['home'] = 1

            if pattern.match(stat.text):
                if quarter == 2:
                    date = datetime.strptime("12:00", "%M:%S")
                elif quarter == 4:
                    date = datetime.strptime("24:00", "%M:%S")
                elif quarter == 6:
                    date = datetime.strptime("36:00", "%M:%S")
                elif quarter == 8:
                    date = datetime.strptime("48:00", "%M:%S")
                elif quarter == 10:
                    date = datetime.strptime("53:00", "%M:%S")
                elif quarter == 12:
                    date = datetime.strptime("58:00", "%M:%S")
                else:
                    date = datetime.strptime("1:03:00", "%H:%M:%S")

                time = datetime.strptime(stat.text[:-2], "%M:%S")
                time = date - time
                time = divmod(time.days * 86400 + time.seconds, 60)
                time = time[0] + time[1] / 60
                time = round(time, 2)

        if score:
            score['time'] = time

            if score['home'] == 1:
                del score['home']
                stat_dist['home'].append(score)
            else:
                del score['home']
                stat_dist['away'].append(score)

        if time is None:
            quarter += 1

    return stat_dist
