from datetime import datetime
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
