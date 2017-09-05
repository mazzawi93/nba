from db import mongo, process_utils
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import poisson, beta


def poisson_distribution(mu, color, dist='pmf'):

    if dist != 'pmf' and dist != 'cdf':
        raise ValueError

    x = np.arange(0, 21)

    if dist == 'pmf':
        y = poisson.pmf(mu=mu, k=x)
        ylabel = 'Pr(X=k)'
    else:
        y = poisson.cdf(mu=mu, k=x)
        ylabel = 'Pr(X' + r'$\leq$' + 'k)'

    plt.plot(x, y, 'k-', linewidth=0.5)
    plt.plot(x, y, color + 'o', label=r'$\lambda = $' + str(mu))
    plt.xticks(np.arange(0,21,5))
    plt.xlabel('k')
    plt.ylabel(ylabel)
    plt.legend()


def beta_distribution(a, b, color, dist='pdf'):


    if dist != 'pdf' and dist != 'cdf':
        raise ValueError

    x = np.arange(0, 1, 0.01)

    if dist == 'pdf':
        y = beta.pdf(x, a, b)
        ylabel = 'PDF'
    else:
        y = beta.cdf(x, a, b)
        ylabel = 'CDF'

    plt.plot(x, y, color + '-', label=r'$\alpha = $' + str(a) + '  ' + r'$\beta = $' + str(b))
    plt.ylabel(ylabel)
    plt.legend()

