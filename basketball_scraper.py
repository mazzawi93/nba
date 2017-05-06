from bs4 import BeautifulSoup
import requests


def team_names():
    # Url for all teams in the NBA
    url = 'http://www.basketball-reference.com/teams/'

    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    # Page also lists defunt franchises, only want currently active teams
    active_teams = soup.find(id="teams_active")

    teams = []

    # Iterate through teams to get the team abbreviation (ex. TOR)
    for active_team in active_teams.find_all('tr', {'class': "full_table"}):
        team_url = active_team.find('a')
        team_name = team_url['href']
        teams.append(team_name[7:10])

    return teams


def season_game_logs(team, year):
    if year > 2017 or year < 1950:
        raise ValueError('Year Value Incorrect')

    url = "http://www.basketball-reference.com/teams/%s/%s/gamelog" % (team, year)

    # The incorrect team won't return 404, but a page with no statistics
    r = requests.get(url)
    soup = BeautifulSoup(r.content, "html.parser")

    season_stats = soup.find(id='tgl_basic')
    try:
        games = season_stats.find('tbody')

        # Loop through every game in a team's season
        for game in games.find_all('tr', {'class': None}):
            match = {}

            # Loop through each stat
            for stat in game.find_all('td'):
                match[stat['data-stat']] = stat.string

            # Separate the two teams' stats
            team1 = {
                'team': team,
                'pts': match['pts'],
                'fg': match['fg'],
                'fga': match['fga'],
                'fg_pct': match['fg_pct'],
                'fg3': match['fg3'],
                'fg3a': match['fg3a'],
                'fg3_pct': match['fg3_pct'],
                'ft': match['ft'],
                'fta': match['fta'],
                'ft_pct': match['ft_pct'],
                'orb': match['orb'],
                'trb': match['trb'],
                'ast': match['ast'],
                'stl': match['stl'],
                'blk': match['blk'],
                'tov': match['tov'],
                'pf': match['pf']
            }

            team2 = {
                'team': match['opp_id'],
                'pts': match['opp_pts'],
                'fg': match['opp_fg'],
                'fga': match['opp_fga'],
                'fg_pct': match['opp_fg_pct'],
                'fg3': match['opp_fg3'],
                'fg3a': match['opp_fg3a'],
                'fg3_pct': match['opp_fg3_pct'],
                'ft': match['opp_ft'],
                'fta': match['opp_fta'],
                'ft_pct': match['opp_ft_pct'],
                'orb': match['opp_orb'],
                'trb': match['opp_trb'],
                'ast': match['opp_ast'],
                'stl': match['opp_stl'],
                'blk': match['opp_blk'],
                'tov': match['opp_tov'],
                'pf': match['opp_pf']
            }

            result = {
                'date': match['date_game']
            }

            # Place the teams in the correct spot depending on who is the home team
            if match['game_location'] is None:
                result['home_result'] = match['game_result']
                result['home'] = team1
                result['away'] = team2
            else:
                if match['game_result'] == 'W':
                    result['home_result'] = 'L'
                else:
                    result['home_result'] = 'W'

                result['home'] = team2
                result['away'] = team1

            print('result')
    except AttributeError:
        print("Doesn't exist")


team_names = team_names()

for team in team_names:
    print(team)
