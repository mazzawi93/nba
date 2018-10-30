def game_dataset(teams=None, season=None, bet=False, abilities=False, mw=0.0394, players=False):
    """
    Create a Pandas DataFrame for the Dixon and Coles model that uses final scores only.
    Can specify the NBA season, month and if betting information should be included.

    :param teams: Team names
    :param season: NBA Season
    :param bet: Betting Lines
    :param players: Include player ID's
    :param mw: Match weight for abilities
    :param abilities: Include team abilities previously generated

    :return: Pandas DataFrame containing game information
    """

    # MongoDB
    m = mongo.Mongo()

    fields = {
        'home': '$home.team',
        'away': '$away.team',
        'hpts': '$home.pts',
        'apts': '$away.pts',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
        'date': 1,
    }

    match = {}

    process_utils.season_check(season, fields, match)

    # Include betting odds
    if bet:
        fields['hbet'] = '$bet.home'
        fields['abet'] = '$bet.away'

    # Include players
    if players:
        fields['hplayers'] = '$hplayers.player'
        fields['aplayers'] = '$aplayers.player'

    # Mongo Pipeline
    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))



    # Get the dynamic dixon coles abilities for each team
    if abilities:

        hmean = np.array([])
        amean = np.array([])

        for week, games in df.groupby('week'):
            ab = m.find_one('dixon_team', {'week': int(week), 'mw': mw})

            if ab is None:
                raise ValueError('Abilities don\'t exist for that match weight')

            # Home Team Advantage
            home_adv = ab.pop('home')

            ab = pd.DataFrame.from_dict(ab)

            home = np.array(ab[games.home])
            away = np.array(ab[games.away])

            hmean = np.append(hmean, home[0] * away[1] * home_adv)
            amean = np.append(amean, home[1] * away[0])

        df['hmean'] = hmean
        df['amean'] = amean

    return df


def player_position(season):
    """
    Get the position that each player played in a season.

    :param season: NBA Season

    :return: DataFrame containing player positions
    """

    # Mongo
    m = mongo.Mongo()

    # Needs to be a list
    if isinstance(season, int):
        season = [season]

    fields = {'seasons': '$seasons'}

    pipeline = [
        {'$project': fields},
        {'$unwind': '$seasons'},
        {'$match': {'seasons.season': {'$in': season}}},
        {'$group': {'_id': {'player': '$_id', 'season': '$seasons.season'},
                    'pos': {'$first': '$seasons.pos'}}},
    ]

    players = m.aggregate('player_season', pipeline)

    df = pd.DataFrame(list(players))
    df = pd.concat([df.drop(['_id'], axis=1), df['_id'].apply(pd.Series)], axis=1)

    # Replace the hybrid positions with their main position
    df.replace('SF-PF', 'SF', inplace=True)
    df.replace('PF-SF', 'PF', inplace=True)
    df.replace('SG-PG', 'SG', inplace=True)
    df.replace('SF-SG', 'SF', inplace=True)
    df.replace('PG-SG', 'PG', inplace=True)
    df.replace('SG-SF', 'SG', inplace=True)
    df.replace('PF-C', 'PF', inplace=True)
    df.replace('C-PF', 'C', inplace=True)

    return df


def player_dataset(season=None, teams=False, position=False, team_ability=False, poisson=False,
                   mw=0.0394, beta=False):
    """
    Create a Pandas DataFrame for player game logs

    :param team_ability: Include team dixon coles abilities
    :param teams: Include team parameters in the dataset
    :param season: NBA Season
    :param beta: Include player's beta mean
    :param mw: Match weight
    :param poisson: Include player poisson abilities
    :param position: Include Player positions

    :return: DataFrame
    """

    # MongoDB
    m = mongo.Mongo()

    fields = {
        'players': '$players',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
        'date': 1,
    }

    match = {}

    process_utils.season_check(season, fields, match)

    player_stats = {'date': 1, 'phome': '$player.home', 'week': 1, 'pts': '$player.pts', 'season': 1,
                    'fouls': '$player.fouls'}

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$unwind': '$players'},
        {'$group': {'_id': {'game': '$_id', 'player': '$players.player'},
                    'player': {'$first': '$players'},
                    'week': {'$first': '$week'},
                    'season': {'$first': '$season'},
                    'date': {'$first': '$date'}}},
        {'$project': player_stats}
    ]

    games = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))
    df = pd.concat([df.drop(['_id'], axis=1), df['_id'].apply(pd.Series)], axis=1)

    # Team Information
    if teams or team_ability:
        dc = game_dataset(season=season, abilities=team_ability)
        df = df.merge(dc, left_on=['game', 'season'], right_on=['_id', 'season'], how='inner')

        for key in ['_id', 'week_y', 'date_y']:
            del df[key]

        df.rename(columns={'week_x': 'week', 'date_x': 'date'}, inplace=True)

    # Player positions
    if position:
        pos_df = player_position(season)
        df = df.merge(pos_df, left_on=['player', 'season'], right_on=['player', 'season'])

    # Player abilities
    if poisson or beta:

        weeks = df.groupby('week')

        if poisson:
            df['poisson'] = 0

        if beta:
            df['a'] = 0
            df['b'] = 0

        for week, games in weeks:

            if poisson:
                abilities = mongo.find_one('player_poisson', {'week': int(week), 'mw': mw},
                                           {'_id': 0, 'week': 0, 'mw': 0})
                abilities = pd.DataFrame.from_dict(abilities, 'index')

                mean = abilities.loc[games['player']][0]
                df.loc[games.index, 'poisson'] = np.array(mean)

            if beta:
                abilities = mongo.find_one('player_beta', {'week': int(week), 'mw': mw}, {'_id': 0, 'week': 0, 'mw': 0})
                abilities = pd.DataFrame.from_dict(abilities, 'index')

                a = abilities.loc[games['player'], 'a']
                b = abilities.loc[games['player'], 'b']
                df.loc[games.index, 'a'] = np.array(a)
                df.loc[games.index, 'b'] = np.array(b)

    df.fillna(0, inplace=True)

    return df


class Players(DynamicDixonColes):
    def __init__(self, mw=0.0394, poisson=False):
        """
            Computes the player abilities for every week by combining the datasets and using the match weight value,
            starting with the 2013 season as the base values for Players.
        """

        super().__init__(mw=mw)

        if poisson:
            self.dist = 'poisson'
        else:
            self.dist = 'beta'

        self.poisson = poisson

        if self.mongo.count('player_' + self.dist, {'mw': self.mw}) == 0:
            print('Player distributions don\'t exist, generating them now...')
            self.player_weekly_abilities()

    def player_weekly_abilities(self):
        """
        Generate weekly player abilities.
        """

        # Delete the abilities in the database if existing
        self.mongo.remove('player_' + self.dist, {'mw': self.mw})

        # Datasets
        start_df = datasets.player_dataset([2013, 2014], teams=True, position=True)
        rest_df = datasets.player_dataset([2015, 2016, 2017, 2018, 2019], teams=True, position=True)

        # Group them by weeks
        weeks_df = rest_df.groupby('week')

        # If a player has played a few games in 2013 and retired, they will be carried through the entire optimisation.
        # Need to find a way to remove players out of the league but leave players who are injured.
        for week, stats in weeks_df:

            players = {'week': int(week), 'mw': self.mw}

            for name, games in start_df.groupby('player'):

                team_pts = np.where(games.phome, games.hpts, games.apts)

                if self.poisson:
                    opt = minimize(nba.player_poisson, x0=games.pts.mean(),
                                   args=(games.pts, games.week, int(week), self.mw))

                    if opt.x[0] < 0:
                        opt.x[0] = 0

                    players[str(name)] = opt.x[0]
                else:


                    a0 = np.array([games.pts.mean(), (team_pts - games.pts).mean()])


                    opt = minimize(nba.player_beta, x0=a0, args=(games.pts, team_pts, games.week, int(week), self.mw))

                    if opt.status == 2:
                        players[str(name)] = {'a': a0[0], 'b': a0[1]}
                    else:
                        players[str(name)] = {'a': opt.x[0], 'b': opt.x[1]}

                    try:
                        teams = stats.groupby('player').get_group(name)
                        teams = teams[teams.week == week]
                        teams = np.unique(np.where(teams.phome, teams.home, teams.away))[0]

                        players[str(name)]['team'] = teams

                        position = stats.groupby('player').get_group(name)
                        position = position.pos.unique()[0]
                        players[str(name)]['position'] = position

                    except KeyError:
                        pass

            self.mongo.insert('player_' + self.dist, players)

            start_df = start_df.append(stats, ignore_index=True)

    def game_predictions(self, seasons, penalty=0.17, star=False, star_factor=85, bet=False):

        self.predictions = game_prediction.dixon_prediction(seasons, mw=self.mw, penalty=penalty, players=True, star=star,
                                                            star_players=star_factor)

    def player_progression(self, player):

        weeks = self.mongo.find('player_' + self.dist, {'mw': self.mw}, {player: 1, '_id': 0})
        abilities = []


        for week in weeks:
            if self.poisson:
                abilities.append(week[player])
            else:
                abilities.append(beta.mean(week[player]['a'], week[player]['b']))

        return np.array(abilities)

    def betting(self, seasons):

        if self.predictions is None:
            self.predictions = game_prediction.dixon_prediction(seasons, mw=self.mw)

        super().betting()


ef dixon_prediction(season, mw=0.044, players=False, star=False, penalty=0.4, star_players=80):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = datasets.game_dataset(season=season, abilities=True, mw=mw, players=players)

    # Win probabilities
    hprob = np.zeros(len(games))
    aprob = np.zeros(len(games))

    # Find Player penalties
    if players:
        games['hpen'], games['apen'] = pu.player_penalty(games, mw, penalty, star_players, star)
    else:
        games['hpen'], games['apen'] = 1, 1

    # Iterate through each game to determine the winner and prediction
    for row in games.itertuples():

        if abilities is not None:
            hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
            amean = abilities[row.away]['att'] * abilities[row.home]['def']
        else:
            hmean = row.hmean
            amean = row.amean

        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(hmean * row.hpen, amean * row.apen)

    # Scale odds so they add to 1
    scale = 1 / (hprob + aprob)
    hprob = hprob * scale
    aprob = aprob * scale

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'_id': games['_id'],
    'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'correct': np.equal(winners, predictions),
                             'season': games.season, 'hprob': hprob, 'aprob': aprob})

    return outcomes


def poisson_prediction(season, mw=0.0394):
    """
    Game prediction using play                       er's poisson means

    :param season: NBA Season
    :param mw: Match weight
    """
    players = datasets.player_dataframe(season, poisson=True, mw=mw)
    games = datasets.game_dataset(season=season)

    games['hmean'], games['amean'] = 0, 0

    for _id, stats in players.groupby('game'):
        hp = np.sum(np.nan_to_num(np.where(stats.phome, stats.poisson, 0)))
        ap = np.sum(np.nan_to_num(np.where(stats.phome, 0, stats.poisson)))

        index = games[games._id == _id].index[0]

        # Set the values
        games.loc[index, 'hmean'] = hp
        games.loc[index, 'amean'] = ap

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean, row.amean)

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes


def beta_prediction(season, mw=0.0394):
    """
    Game prediction using player beta means (sum)

    :param season: NBA season
    :param mw: Match weight
    """
    players = datasets.player_dataframe(season, beta=True, mw=mw)
    games = datasets.game_dataset(season=season, abilities=True)

    games['hbeta'], games['abeta'] = 0, 0

    for _id, stats in players.groupby('game'):
        hp = np.sum(np.nan_to_num(np.where(stats.phome, beta.mean(stats.a, stats.b), 0)))
        ap = np.sum(np.nan_to_num(np.where(stats.phome, 0, beta.mean(stats.a, stats.b))))

        index = games[games._id == _id].index[0]

        # Set the values
        games.loc[index, 'hbeta'] = hp
        games.loc[index, 'abeta'] = ap

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hbeta, row.amean * row.abeta)

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes
