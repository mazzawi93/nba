import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
import datetime


year = 2019
url = 'https://www.atptour.com/en/scores/results-archive?year=' + str(year)

response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')


tourney = []

for tournament in soup.find_all('tr', {'class': 'tourney-result'}):
    bruh = {
        'season': year,
        'name': tournament.find('span', {'class': 'tourney-title'}).text.lstrip().rstrip(),
        'location': tournament.find('span', {'class': 'tourney-location'}).text.lstrip().rstrip(),
        'start_date': datetime.datetime.strptime(tournament.find('span', {'class': 'tourney-dates'}).text.lstrip().rstrip(), '%Y.%m.%d')
        #'prize_money': tournament.find('td', {'class': 'fin-commit'}).find('span', {'class': 'item-value'}).text.lstrip().rstrip()
    }
    tourney.append(bruh)

df = pd.DataFrame(tourney)
