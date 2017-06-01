import matplotlib
import matplotlib.pyplot as plt
from pymongo import MongoClient
import pandas as pd

stat_names = ['orb', 'drb', 'fgm', 'fga', 'assist', 'points', 'ftm', 'fta',
              'fg3a', 'fg3m', 'turnover', 'foul', 'timeout', 'sub']


class stat_dataframe:
    def __init__(self, stat=None):

        if stat is None:
            stat = ['points']

        for key in stat:
            if key not in stat_names:
                raise ValueError('Incorrect Statistic Key')

        self.stat = stat

        print('Processing %s time data...' % self.stat)

        self.data = self.get_times()

    def get_times(self):

        time_data = {}
        client = MongoClient()
        db = client.basketball
        collection = db.game_log

        locations = ['home_time', 'away_time']

        for loc in locations:
            games = collection.find({}, {loc: 1})

            for game in games:
                for stat in game[loc]:

                    time = int(stat['time']) + 1

                    for key in self.stat:
                        if key in stat:

                            if time not in time_data:
                                time_data[time] = {}

                            if key not in time_data[time]:
                                time_data[time][key] = stat[key]

                            else:
                                time_data[time][key] = time_data[time][key] + stat[key]

        data = pd.DataFrame(time_data)
        data = data.transpose()

        return data

matplotlib.style.use('ggplot')

stats = stat_dataframe()

ax = stats.data.plot(title='Points' + ' Minute Distribution for Last 6 years of NBA')
ax.set_xlabel('Minute')
ax.set_ylabel('Points')
ax.axvline(48, linestyle='dashed', color='black', linewidth=1)
ax.axvline(12, linestyle='dashed', color='black', linewidth=0.5)
ax.axvline(24, linestyle='dashed', color='black', linewidth=0.5)
ax.axvline(36, linestyle='dashed', color='black', linewidth=0.5)
plt.show()
