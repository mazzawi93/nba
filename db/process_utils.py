import string

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL',
         'MEM', 'MIA',
         'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']


def season_check(season):
    """
    Helper function to determine if season is correctly entered
    :param season: List of seasons or None
    """

    if not isinstance(season, list):
        if season is not None:
            raise TypeError("Season must be a list for query purposes")
    else:
        for year in season:
            if year < 2012 or year > 2017:
                raise ValueError("Years must be within the range 2012-2017")


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


def name_teams(nba, nteams=None):
    if nba is True:
        return teams
    else:
        team_names = []
        for i in range(nteams):
            if i < 26:
                team_names.append(string.ascii_uppercase[i])
            else:
                team_names.append(string.ascii_uppercase[i - 26] + string.ascii_uppercase[i - 26])

        return team_names
