from basketball import nba_model
import pandas as pd
import numpy as np
from db import datasets
ball = nba_model(0.044, 'rolling_low', None, 7)
today = ball.today_games(bets_only=False, file_name='rolling_attack_mar6_bets.csv')

pred = ball.predict(seasons=[2019])
ab = datasets.team_abilities(0.044, 'rolling_low', None, 7)
ab.to_csv('abilities.csv', index=False)

#1.16 1.6


"""Simultaneous kelly is done by taking the product of 1-kelly for all simultaneous wagers and then multiplying each kelly amount by that product. So if I have two simultaneous bets, one calling for a full kelly wager of 2.5% and another calling for a 2% wager then I would bet (1-.025)*(1-.02)*2.5% = 2.387% on the first wager and (1-.025)*(1-.02)*2% = 1.91% on the second wager."""
