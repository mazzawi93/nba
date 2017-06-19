from scipy.stats import poisson


def attack_constraint(params, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - 100


def dixon_coles(abilities, matches, teams):
    """
    This is the likelihood function for the Dixon Coles model.
    :param abilities:
    :param matches:
    :param teams:
    :return: Likelihood
    """
    total = 0

    num = len(teams)

    for game in matches:
        hteam, ateam = game[0], game[2]
        hpts, apts = game[1], game[3]

        # Determine ability indexes
        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == hteam]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == ateam]:
            ai = i

        # Home and Away Poisson intensities
        hmean = abilities[num * 2] * abilities[hi] * abilities[ai + num]
        amean = abilities[hi + num] * abilities[ai]

        # Log Likelihood
        total += poisson.logpmf(hpts, hmean) + poisson.logpmf(apts, amean)

    return -total


def dixon_robinson(abilities, matches, teams, model):
    total = 0

    # Number of teams
    num = len(teams)

    for game in matches:

        # Team Names
        home, away = game[0], game[2]

        # Team Indexes for the ability array
        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == home]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == away]:
            ai = i

        like = 0
        hp, ap = 0, 0

        # Iterate through each point scored
        for point in game[4]:

            if model > 1:
                time_stamp = float(point['time'])

                if (11 / 48) < time_stamp <= (12 / 48):
                    time = abilities[num * 2 + 1]
                elif (23 / 48) < time_stamp <= (24 / 48):
                    time = abilities[num * 2 + 2]
                elif (35 / 48) < time_stamp <= (36 / 48):
                    time = abilities[num * 2 + 3]
                elif (47 / 48) < time_stamp <= (48 / 48):
                    time = abilities[num * 2 + 4]
                else:
                    time = 1

            if point['home'] == 0:
                hp += int(point['points'])
                mean = abilities[hi] * abilities[ai + num] * abilities[num * 2]

                like += poisson.logpmf(hp, mean)
            else:
                ap += int(point['points'])
                mean = abilities[hi + num] * abilities[ai]

                like += poisson.logpmf(ap, mean)

            if model > 1:
                like += time
        total += like - poisson.logpmf(hp, (abilities[hi] * abilities[ai + num] * abilities[num * 2])) - poisson.logpmf(
            ap, (abilities[hi + num] * abilities[ai]))

    return -total
