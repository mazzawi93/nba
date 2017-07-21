import string

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM',
         'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']


def season_check(season, fields, match):
    """
    Add season to the mongoDB query fields
    :param season: NBA season
    :param fields: MongoDB $project fields
    :param match: MongoDB $match field
    """

    if season is not None:

        # Convert season to list because aggregation uses $in
        if isinstance(season, int):
            season = [season]

        # Raise error if incorrect type was given
        if not isinstance(season, list):
            raise TypeError("Season must be a list for query purposes")
        else:
            # Raise error if year value is incorrect
            for year in season:
                if year < 2013 or year > 2017:
                    raise ValueError("Years must be within the range 2013-2017")

            # Add season for aggregation query
            fields['season'] = 1
            match['season'] = {'$in': season}


def month_check(month, fields, match):
    """
    Add month to the mongoDB query fields
    :param month: Calendar Month
    :param fields: MongoDB Project fields
    :param match: MongoDB Match fields
    """

    if month is not None:
        if isinstance(month, int):
            month = [month]

        if not isinstance(month, list):
            raise TypeError("Incorrect type entered for month (int or list)")

        fields['month'] = {'$month': '$date'}
        match['month'] = {'$in': month}


def team_check(team):
    """
    Helper function to determine if teams were entered correctly
    :param team: List of NBA Teams
    :return: List of Teams
    """

    if not isinstance(team, list):
        if team is not None:
            raise TypeError("Team must be a list for query purposes")
    else:
        for city in team:
            if city not in teams:
                raise ValueError("Team not in database")


def name_teams(test, nteams=None):
    """
    Team names for the datasets.

    :param test: True for fabricated dataset.  Team names become letters
    :param nteams: Number of teams
    :return: Team names
    """

    # Return nba team names
    if test is False:
        return teams
    # Assign letters of the alphabet as team names
    else:
        team_names = []
        for i in range(nteams):
            if i < 26:
                team_names.append(string.ascii_uppercase[i])
            else:
                team_names.append(string.ascii_uppercase[i - 26] + string.ascii_uppercase[i - 26])

        return team_names
