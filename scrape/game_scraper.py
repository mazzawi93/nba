from datetime import datetime
from scrape import scrape_utils
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient


class GameScraper:

    def __init__(self):

        # Scrape the NBA Team Names from Basketball Reference
        self.teams = scrape_utils.team_names()
        self.years = range(2012, 2018)

        # MongoDB
        client = MongoClient()
        self.db = client.basketball

    def season_game_logs(self, team, year):
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
            collection = self.db.game_log

            # Games table on HTML
            games = season_stats.find('tbody')

            # Loop through every game in a team's season
            for game in games.find_all('tr', {'class': None}):

                match = {}

                # Find the URL for a game's play by play stat for the time for each stat
                pbp = game.find('a')
                pbp_url = 'http://www.basketball-reference.com/boxscores/pbp' + pbp['href'][-18:]
                pbp_stats = scrape_utils.stat_distribution(pbp_url)

                # print(pbp_stats)

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
                          'season': year,
                          'home_time': pbp_stats['home'],
                          'away_time': pbp_stats['away']}

                # Place the teams in the correct spot depending on who is the home team
                if match['game_location'] is None:
                    result['home'] = team1
                    result['away'] = team2
                else:
                    result['home'] = team2
                    result['away'] = team1

                # Store match result
                result['result'] = scrape_utils.determine_home_win(match['game_location'], match['game_result'])

                if collection.find_one(result) is None:
                    collection.insert_one(result)
        except AttributeError:
            print("%s doesn't exist" % team)

    def team_season_stats(self, team):
        """
        Scrape a team's season stats for every year and store it in the database
        :param team: NBA Team
        """

        # Get HTML Content
        url = 'http://www.basketball-reference.com/teams/%s/stats_per_game_totals.html' % team
        r = requests.get(url)
        soup = BeautifulSoup(r.content, "html.parser")

        # MongoDB Collection
        collection = self.db.team_season

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

    def scrape_all(self):
        """
        Iterate through each team and year to get season game logs and yearly stats
        """

        print("Scraping NBA Data...")

        # Iterate through each team and year
        for team in self.teams:
            self.team_season_stats(team)
            for year in self.years:
                print("%s (%s)" % (team, year))
                self.season_game_logs(team, year)
