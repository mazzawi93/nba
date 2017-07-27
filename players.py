from db import datasets
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression


class Player:
    def __init__(self, player):
        self.player = player

        # Create testing and training datasets
        train = datasets.player_dataframe(player, season=[2014, 2015, 2016])
        test = datasets.player_dataframe(player, season=2017)

        # Create output vectors
        y_train = train.pop('points')
        y_test = test.pop('points')

        self.data = {
            'train': {
                'x': train,
                'y': y_train
            },
            'test': {
                'x': test,
                'y': y_test
            }
        }

        self.neural = MLPRegressor()
        self.neural.fit(train, y_train)

        self.linear = LinearRegression()
        self.linear.fit(train, y_train)
