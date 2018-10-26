from scrape import player_scraper, team_scraper, scrape_utils
from db import mongo

# Get all team games and yearly stats
for team in scrape_utils.team_names():

    # Team Season Stats
    print(team)
    team_scraper.team_season_stats(team)

    for year in range(2013, 2020):
        print(year)

        # Game Logs
        team_scraper.season_game_logs(team, year)

        # Starting Lineups
        player_scraper.get_starting_lineups(team, year)

# Get betting lines (By Year) need from 2014
for year in range(2013, 2020):
    team_scraper.betting_lines(year)

m = mongo.Mongo()

# Game Information (Box Score and Play by Play)
for year in range(2018, 2020):
    for game in m.find('game_log', {'season': year}, {'_id': 1}):
        team_scraper.play_by_play(game['_id'])
        player_scraper.player_box_score(game['_id'])
        print(game['_id'])


# Get player information
for player in scrape_utils.get_active_players():
    print(player)
    player_scraper.player_per_game(player)
