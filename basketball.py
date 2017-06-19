from db import test_set


class Basketball:
    def __init__(self, nba, nteams=None, ngames=None):

        self.data = None

        if nba is True:

            self.nba_data(nteams, ngames)
        else:
            # Checking the number of teams
            if nteams is None:
                raise TypeError('Number of teams must be defined.')
            elif nteams < 2:
                raise ValueError('There must be at least two teams.')

            # Check the number of games played between both teams
            if ngames is None:
                raise TypeError('Number of games must be defined.')
            elif ngames % 2 != 0:
                raise ValueError('The number of games must be even so there is equal home and away.')

            self.test_data()

    def nba_data(self, nteams, ngames):
        self.data = 2

    def test_data(self):
        self.data = 3
