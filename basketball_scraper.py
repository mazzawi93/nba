from bs4 import BeautifulSoup
import requests

url = "http://www.basketball-reference.com/teams"
r = requests.get(url)

soup = BeautifulSoup(r.content, "html.parser")

teams = soup.find(id="teams_active")

for active_team in teams.find_all('tr', {"class": "full_table"}):
    url_plus = active_team.find('a')

    # print(url + url_plus['href'] + 'gamelogs')
    # print(url_plus.string)
    print(active_team)
