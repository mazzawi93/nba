def rename_team(team):
    """
    Rename a team that has relocated to keep the database consistent

    :param team: Team Abbreviation to be named
    :return: Changed team name if the team has relocated, otherwise the same name is returned

    """

    # Rename relocated team to current abbreviation
    if team == 'NJN':
        team = 'BRK'
    elif team == 'CHA':
        team = 'CHO'
    elif team == 'NOH':
        team = 'NOP'

    return team


def determine_home_win(location, result):
    """
    Determine the result of the home team given the location and result for a a specific team

    :param location: Location of the game (None for Home, @ for Away)
    :param result: Result of the game (W for Win, L for Loss)
    :return: 1 or -1 for the home result
    :raises Value Error: If result is not W or L, and if location is not None or @

    """

    if result != 'W' and result != 'L':
        raise ValueError('The game result is incorrect, must be W or L')

    if location is not None and location != '@':
        raise ValueError('Location is incorrectly entered')

    # Determine Home Winner
    if location is None:
        if result == 'W':
            return 1
        else:
            return -1
    else:
        if result == 'L':
            return 1
        else:
            return -1


