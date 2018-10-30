import string
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


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

    if location != 0 and location != '@':
        raise ValueError('Location is incorrectly entered')

    # Determine Home Winner
    if location is 0:
        if result == 'W':
            return 1
        else:
            return -1
    else:
        if result == 'L':
            return 1
        else:
            return -1


def field_goal_update(player, stat, play, make):
    """
    Update the parameters depending on the shot
    :param player: NBA player
    :param stat: Statistic in game
    :param play: Play dict
    :param make: True for successful shot
    :return:
    """
    # Get player name/id
    play['player'] = player.rsplit('/', 1)[-1].rsplit('.', 1)[0]

    # Record if there was an assist
    if 'assist' in stat:
        play['assist'] = 1

    # Determine the type of basket scored
    if '3-pt' in stat:
        if make:
            play['points'] = 3
            play['fgm'] = 1
            play['fg3m'] = 1
        play['fga'] = 1
        play['fg3a'] = 1
    elif '2-pt' in stat:
        if make:
            play['points'] = 2
            play['fgm'] = 1
        play['fga'] = 1
    elif 'free' in stat:
        if make:
            play['points'] = 1
            play['ftm'] = 1
        play['fta'] = 1


def play_time(quarter, time_text):
    """
    Determine the exact time a play happens in a play by play log.
    The times start at 0 from each quarter but the overall time is wanted.

    :param quarter: Nba quarter
    :param time_text: Time stamp
    :return: Total time
    """

    # There are two blank rows between quarters
    if quarter == 2:
        base = datetime.strptime("12:00", "%M:%S")
    elif quarter == 4:
        base = datetime.strptime("24:00", "%M:%S")
    elif quarter == 6:
        base = datetime.strptime("36:00", "%M:%S")
    elif quarter == 8:
        base = datetime.strptime("48:00", "%M:%S")
    elif quarter == 10:
        base = datetime.strptime("53:00", "%M:%S")
    elif quarter == 12:
        base = datetime.strptime("58:00", "%M:%S")
    else:
        base = datetime.strptime("1:03:00", "%H:%M:%S")

    # Adjust the time
    time = datetime.strptime(time_text, "%M:%S")
    time = base - time
    time = divmod(time.days * 86400 + time.seconds, 60)
    time = time[0] + time[1] / 60
    return round(time, 2)


def stat_parse(stat_name, stat):
    """
    Parse a scraped stat to store the correct type
    :param stat_name: Stat Name
    :param stat: Stat Value
    :return: the statistic in the correct type
    """

    try:
        if stat_name == 'mp':
            if len(stat) == 4:
                stat = '0' + stat
            return int(stat[0:2]) * 60 + int(stat[3:5])
        elif len(stat) < 4:
            return int(stat)
        elif stat[0] == '.' or stat.string[1] == '.':
            return float(stat)

        else:
            return stat
    except TypeError:
        return 0
    except ValueError:
        return stat

def oddsportal_login():
    """ Log in for oddsportal so that all odds are available."""

    # Selenium web browser
    browser = webdriver.Chrome('chromedriver')

    # Go to login page
    browser.get('https://www.oddsportal.com/login/')

    # Fill in username
    browser.find_element_by_xpath('//*[@id="login-username1"]').send_keys('tonymazz')

    # fill in password
    pass_input = browser.find_element_by_xpath('//*[@id="login-password1"]')

    # Input Password
    pass_input.send_keys('')
    pass_input.send_keys(Keys.ENTER)

    # Click login

    return browser
