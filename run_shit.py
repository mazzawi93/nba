from basketball import nba_model
import pandas as pd
import numpy as np
from db import mongo
import datetime
from models import prediction_utils
import json

ball = nba_model(0.044, 100, 1, 7)

today = ball.today_games(bets_only=False, file_name='jan14_home_bets.csv')

today = ball.today_games(bets_only=False, file_name='jan14_away_bets.csv')
pred = ball.predict(seasons=[2017, 2018, 2019])
betting = ball.games_to_bet(pred, sportsbooks=['SportsInteraction', 'Pinnacle Sports', 'bet365'], R_percent=False)

ball.betting_ranges(pred, file_name='attack_100_home_betting_ranges.xlsx', years=[[2017],[2018],[2019]], to_file=True, home=True)
ball.betting_ranges(pred, file_name='attack_100_away_betting_ranges.xlsx', years=[[2017],[2018],[2019]], to_file=True, home=False)

ball = nba_model(0.044, 'rolling_low', None, 7)
pred = ball.predict(seasons=[2017, 2018, 2019], players=True)
ball.betting_ranges(pred, file_name='attack_rolling_best_player_home_betting_ranges.xlsx', years=[[2017],[2018],[2019]], to_file=True, home=True)
ball.betting_ranges(pred, file_name='attack_rolling_best_player_away_betting_ranges.xlsx', years=[[2017],[2018],[2019]], to_file=True, home=False)


low_r = 1
high_r = 3

# OPTIMAL BET
ball = nba_model(0.044, 100, 1, 7)
pred = ball.predict(seasons=[2019])
betting = ball.games_to_bet(pred, sportsbooks=['SportsInteraction', 'Pinnacle Sports', 'bet365'], R_percent=False)
home = True
op = pd.DataFrame()

op = pd.DataFrame()

ball = nba_model(0.044, 100, 1, 7)
pred = ball.predict(seasons=[2017, 2018, 2019])
betting = ball.games_to_bet(pred, sportsbooks=['SportsInteraction', 'Pinnacle Sports', 'bet365'], R_percent=False)

op = optimal_R(op, betting, True, 100, '100_attack_home_betting_ranges_minus2weeks_')
op = optimal_R(op, betting, False, 100,'100_attack_away_betting_ranges_minus2weeks_')

ball = nba_model(0.044, 'rolling_low', 1, 7)
pred = ball.predict(seasons=[2017, 2018, 2019])
betting = ball.games_to_bet(pred, sportsbooks=['SportsInteraction', 'Pinnacle Sports', 'bet365'], R_percent=False)

op = optimal_R(op, betting, True, 'rolling_low', 'rolling_attack_home_betting_ranges_minus2weeks_')
op = optimal_R(op, betting, False, 'rolling_low','rolling_attack_away_betting_ranges_minus2weeks_')

pred = ball.predict(seasons=[2017, 2018, 2019], players=True)

op = optimal_R(op, betting, True, 'rolling_low_bp', 'rolling_attack_best_player_home_betting_ranges_minus2weeks_')
op = optimal_R(op, betting, False, 'rolling_low_bp','rolling_attack_best_player_away_betting_ranges_minus2weeks_')

op.to_csv('optimal_R.csv', index=False)

def optimal_R(op, betting, home, attack, benchmark_filename):
    for season in betting.season.unique():
        games = betting[betting.season == season]
        # Get Optimal R for the first two weeks of the season
        min_date = games.date.min() + datetime.timedelta(days=14)
        early_games = games[games.date < min_date]
        other_games = games[games.date >= min_date]
        # Betting ranges without first 2 weeks
        ball.betting_ranges(pred, file_name=benchmark_filename + str(season) + '.xlsx', years=[[season]], to_file=True, home=home)
        #optimal_bet
        df = {
            'bankroll': 2000,
            'bet_total': 0,
            'bet_count': 0,
            'bet_revenue': 0
            }
        for day in other_games.date.unique():
            games_before = betting[betting.date < pd.Timestamp(day)]
            day_games = betting[betting.date == pd.Timestamp(day)]
            # Get the optimal R
            optimal_df = ball.betting_ranges(games_before, home = home, years=[[season]])
            optimal_df = optimal_df.loc[optimal_df.profit.idxmax()]
            if home:
                games = day_games.loc[day_games.groupby('_id')['home_R'].idxmax()].reset_index(drop=True)
            else:
                games = day_games.loc[day_games.groupby('_id')['away_R'].idxmax()].reset_index(drop=True)
            for index, game in games.iterrows():
                if home:
                    bet = (game.home_R < optimal_df.high_r) & (game.home_R > optimal_df.low_r)
                    odds = game.home_odds
                else:
                    bet = (game.away_R < optimal_df.high_r) & (game.away_R > optimal_df.low_r)
                    odds = game.away_odds
                if bet:
                    bet_amount = round(1/(odds* 1.5 * 10) * df['bankroll'], 2)
                    df['bankroll'] = df['bankroll'] - bet_amount
                    df['bet_total'] += bet_amount
                    df['bet_count'] += 1
                if home:
                    if bet:
                        if(game.home_pts > game.away_pts):
                            df['bankroll'] = df['bankroll'] + round(bet_amount*odds, 2)
                            df['bet_revenue'] += round(bet_amount*odds, 2)
                else:
                    if bet:
                        if(game.away_pts > game.home_pts):
                            df['bankroll'] = df['bankroll'] + round(bet_amount*odds, 2)
                            df['bet_revenue'] += round(bet_amount*odds, 2)
        df['profit'] = df['bet_revenue'] - df['bet_total']
        df['season'] = season
        df['attack'] = attack
        df['home'] = home
        op.append(df, ignore_index=True)
    return op
