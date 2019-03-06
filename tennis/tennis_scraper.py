import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
import datetime
from selenium import webdriver


def bs_request(url):
	# helper function to turn html ito bs4 parse goodness
	headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/602.4.8 (KHTML, like Gecko) Version/10.0.3 Safari/602.4.8'}
	response = requests.get(url,headers=headers)
	soup = BeautifulSoup(response.text, 'html.parser')
	return(soup)

def scrape_year(year):
	###
	#
	# Get all tournaments in a given year
	#
	# grab that year's atp site data
	url = 'https://www.atptour.com/en/scores/results-archive?year=' + str(year)
	soup = bs_request(url)
	tourney = []
	tournmanets = soup.find_all('tr', {'class': 'tourney-result'})
	t=tournmanets[0]
	t.find('td', {'class': 'fin-commit'})
	# get all tournament data for both has data and  not data cases
	# TODO: figure out if they are currently running
	for tournament in soup.find_all('tr', {'class': 'tourney-result'}):
		# check that the tourney has started
		if tournament.find('a', {'class': 'button-border'}):
		    bruh = {
		        'season': year,
		        'name': tournament.find('span', {'class': 'tourney-title'}).text.lstrip().rstrip(),
		        'location': tournament.find('span', {'class': 'tourney-location'}).text.lstrip().rstrip(),
		        'start_date': datetime.datetime.strptime(tournament.find('span', {'class': 'tourney-dates'}).text.lstrip().rstrip(), '%Y.%m.%d'),
		        'prize_money': tournament.find('td', {'class': 'fin-commit'}).find('span', {'class': 'item-value'}).text.lstrip().rstrip(),
		        'url': 'https://www.atptour.com/'+tournament.find('a', {'class': 'button-border'})['href']
		    }
		else:
			bruh = {
		        'season': year,
		        'name': tournament.find('span', {'class': 'tourney-title'}).text.lstrip().rstrip(),
		        'location': tournament.find('span', {'class': 'tourney-location'}).text.lstrip().rstrip(),
		        'start_date': datetime.datetime.strptime(tournament.find('span', {'class': 'tourney-dates'}).text.lstrip().rstrip(), '%Y.%m.%d'),
		        'prize_money': '',
		        'url': ''
		    }
		tourney.append(bruh)
	df = pd.DataFrame(tourney)
	return(df)


def scrape_tournament(tourney_url):
	###
	#
	# function that scrapes historic game outcomes
	#
	soup = bs_request(tourney_url)
	all_entries =[]
	### get the names of the round
	round_names = []
	# get all table heads for the round name
	for the_round in soup.find('table', {'class': 'day-table'}).find_all('thead'):
		rnd_names = the_round.text.lstrip().rstrip()
		round_names.append(rnd_names)
	# get all result bodys
	all_tbodys = soup.find('table', {'class': 'day-table'}).find_all('tbody')
	for i in range(len(all_tbodys)):
		the_round = round_names[i]
		# get all players
		for result in all_tbodys[i].find_all('tr'):
			results = result.find_all('td', {'class': 'day-table-name'})
			winner_name = results[0].text.lstrip().rstrip()
			winner_url = results[0].find('a')['href']
			loser_name = results[1].text.lstrip().rstrip()
			loser_url = results[1].find('a')['href']
			# get the link to the score page
			try:
				round_data_url = result.find('td',{'class':'day-table-score'}).find('a')['href']
			except KeyError:
				round_data_url = ''
			all_entries.append((the_round,winner_name,winner_url,loser_name,loser_url,round_data_url))
	# turninto pandas df df
	df = pd.DataFrame(all_entries,columns=['round','winnner','winner_url','loser','loser_url','match_url'])
	return(df)

def get_match_stats(match_url):
	###
	#
	# scrape the statisitcs of a match
	#
	# takes a match url and returns a list of dictionaries of metrics
	# where index 0 in the list won and index 1 lost
	#
	# TODO: TURN THIS INTO A DATA FRAME
	the_match = 'https://www.atptour.com/'+match_url
	# initialize match results
	match_res = [{},{}]
	#get site
	soup = bs_request(the_match)
	## get the points
	scores = soup.find('table',{'class':'scores-table'}).find('tbody').find_all('tr')
	for i in range(2):
		score = scores[i]
		is_winner = 0
		#check if this person has won
		if score.find('td',{'class':'won-game'}) is not None:
			winner_index = i
			is_winner = 1
		player_scores = [x.text.lstrip().rstrip() for x in score.find_all('span')]
		# get rid of blanks
		player_scores = [sc for sc in player_scores if sc != '']
		match_res[is_winner]['scores'] = player_scores
	###### Get the rest of the stats
	# left side
	left = soup.find('table',{'class':'match-stats-table'}).find_all('td',{'class','match-stats-number-left'})
	left_stats = [x.find('span').text.lstrip().rstrip() for x in left]
	#right side
	right = soup.find('table',{'class':'match-stats-table'}).find_all('td',{'class','match-stats-number-right'})
	right_stats = [x.find('span').text.lstrip().rstrip() for x in right]
	#labels
	labs = soup.find('table',{'class':'match-stats-table'}).find_all('td',{'class','match-stats-label'})
	labs = [x.text.lstrip().rstrip() for x in labs]
	labs = [x.lower().replace(' ','_') for x in labs]
	# rearrainge left and right based on who won
	if winner_index == 0:
		winner_stats = left_stats
		loser_stats = right_stats
	else:
		winner_stats = right_stats
		loser_stats = left_stats
	# update metrics dicts
	for k,wv,lv in zip(labs,winner_stats,loser_stats):
		match_res[0][k] = wv
		match_res[1][k] = lv
	return(match_res)


# examples

#year = 2019
# get the tourneys for the year
#df = scrape_year(year)
# get one tournament result
#test_url = df.url[0]
#tourn = scrape_tournament(df.url[1])
# get one match result
#get_match_stats(tourn.match_url[1])

def player_ranking(url):

    #url = 'https://www.atptour.com/en/players/rafael-nadal/n409/rankings-history'
    soup = bs_request(url)

    rankings = soup.find('table', {'class': 'mega-table'}).find('tbody')

    all_weeks = []

    for ranking in rankings.find_all('tr'):
        r = ranking.find_all('td')
        derp = {
            'date': datetime.datetime.strptime(r[0].text.lstrip().rstrip(), '%Y.%m.%d'),
            'singles_ranking': r[1].text.lstrip().rstrip(),
            'doubles_ranking': r[2].text.lstrip().rstrip()
        }
        all_weeks.append(derp)

    return pd.DataFrame(all_weeks)


def scrape_betting_page(game_date):

    browser = webdriver.Chrome('chromedriver')

    url = 'https://classic.sportsbookreview.com/betting-odds/tennis/?date=' + datetime.datetime.strftime(game_date, '%Y%m%d')
    browser.get(url)

    # Sportsbooks
    sb = browser.find_elements_by_id('bookName')
    sportsbooks = ['Opening']

    # Create list of sportsbooks
    for sportbook in sb:
        if len(sportbook.text) > 1:
            sportsbooks.append(sportbook.text)

    # Get team names and odds
    games = browser.find_elements_by_class_name('eventLine')

    df = pd.DataFrame()

    for game in games:

        team_elements = game.find_elements_by_tag_name('a')

        # Get Player names
        player_1 = team_elements[0].text
        player_2 = team_elements[1].text

        odds_elements = game.find_elements_by_class_name('eventLine-book-value')

        # Odds for each player by sportsbooks
        player_1_odds = []
        player_2_odds = []
        i = 0

        for game_odds in odds_elements:
            if i > 0:
                if i % 2 != 0:
                    player_1_odds.append(game_odds.text)
                else:
                    player_2_odds.append(game_odds.text)
            i += 1

        # Scrapes rows with no data so don't insert those
        if len(player_1_odds) > 0:
            player_df = pd.DataFrame({'player_1': player_1, 'player_2': player_2, 'sportsbook': sportsbooks, 'odds_1': player_1_odds, 'odds_2': player_2_odds})
            player_df = player_df[(player_df.odds_1 != '') & (player_df.odds_2 != '')]
            df = df.append(player_df, ignore_index=True)

    # Convert to decimal odds
    df['odds_1'] = pd.to_numeric(df['odds_1'])
    df['odds_1'] = np.where(df['odds_1'] >= 0, round(df.odds_1/100 + 1, 2), round(100/abs(df.odds_1)+1, 2))

    df['odds_2'] = pd.to_numeric(df['odds_2'])
    df['odds_2'] = np.where(df['odds_2'] >= 0, round(df.odds_2/100 + 1, 2), round(100/abs(df.odds_2)+1, 2))

    # Tennis is played all over the world so timezones might fuck us up
    if game_date is None:
        game_date = datetime.date.today()
    df['date'] = game_date

    browser.close()

    return df

# TODO: get the list of tournement sTandings from player urls: https://www.atptour.com/en/players/rafael-nadal/n409/rankings-history
# TODO: get odds
