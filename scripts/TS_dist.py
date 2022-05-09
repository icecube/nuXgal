import argparse
from re import template

import numpy as np
import pandas as pd

from KIPAC.nuXgal.CskyEventGenerator import CskyEventGenerator
from KIPAC.nuXgal.NeutrinoSample import NeutrinoSample
from KIPAC.nuXgal.WeightedNeutrinoSample import WeightedNeutrinoSample
from KIPAC.nuXgal.WeightedLikelihood import WeightedLikelihood
from KIPAC.nuXgal.Likelihood import Likelihood

import matplotlib.pyplot as plt
import healpy as hp

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--n-trials', help='Number of trials', type=int)
    parser.add_argument('-i', '--n-inject', help='Number of neutrinos to inject', type=int, nargs='+')
    parser.add_argument('-o', '--output')
    parser.add_argument('--gamma', help='Injection spectrum power law index', default=2.5, type=float)
    parser.add_argument('--compute-std', action='store_true')
    #parser.add_argument('--analysis', nargs='+', default=['weighted'])
    args = parser.parse_args()
    print(args.n_trials, args.output)

    nrows = args.n_trials * len(args.n_inject)
    results = {
        # injection columns
        'n_inj': np.zeros(nrows),
        'flux_inj': np.zeros(nrows),
        'gamma': np.zeros(nrows),
        # weighted nuXgal fit results
        'weighted_f_fit': np.zeros(nrows),
        'weighted_n_fit': np.zeros(nrows),
        'weighted_TS': np.zeros(nrows),
        'weighted_flux_fit': np.zeros(nrows),
        # unweighted nuXgal fit results
        'f_fit': np.zeros(nrows),
        'n_fit': np.zeros(nrows),
        'TS': np.zeros(nrows),
        'flux_fit': np.zeros(nrows),
        # template fit results
        'template_n_fit': np.zeros(nrows),
        'template_TS': np.zeros(nrows),
        'template_TS': np.zeros(nrows),
        'template_flux_fit': np.zeros(nrows),
    }

    weighted_llh = WeightedLikelihood(10, 'WISE', args.compute_std, 0, 1, 50, gamma=args.gamma)
    unweighted_llh = Likelihood(10, 'WISE', args.compute_std, 0, 1, 50, gamma=args.gamma)

    eg = weighted_llh.event_generator
    eg.updateGamma(args.gamma)

    counter = 0
    for n_inject in args.n_inject:
        for i in range(args.n_trials):
            trial, nexc = eg.trial_runner.get_one_trial(n_inject)
            results['n_inj'][counter] = n_inject
            results['flux_inj'][counter] = eg.trial_runner.to_dNdE(n_inject, E0=1e5) / (4*np.pi*weighted_llh.f_sky)
            results['gamma'][counter] = args.gamma

            weighted_results = weighted_analysis(weighted_llh, trial, args.gamma)
            for key in weighted_results:
                results[key][counter] = weighted_results[key]

            unweighted_results = unweighted_analysis(unweighted_llh, trial)
            for key in unweighted_results:
                results[key][counter] = unweighted_results[key]

            template_results = template_analysis(trial, nexc, eg.trial_runner)
            for key in template_results:
                results[key][counter] = template_results[key]

            counter += 1

    data = pd.DataFrame(results)
    data.to_csv(args.output, index=False)

def weighted_analysis(llh, trial, gamma):
    ns = WeightedNeutrinoSample()
    ns.inputTrial(trial)
    llh.inputData(ns)
    ns.updateCountsMap(gamma, llh.event_generator.ana)
    result_dict = {}
    result_dict['weighted_f_fit'], result_dict['weighted_TS'] = llh.minimize__lnL()
    deweighted_f_fit = llh.weighted_f_to_f(result_dict['weighted_f_fit'], gamma)
    result_dict['weighted_n_fit'] = llh.Ncount * deweighted_f_fit
    result_dict['weighted_flux_fit'] = llh.event_generator.trial_runner.to_dNdE(result_dict['weighted_n_fit'], E0=1e5) / (4*np.pi*llh.f_sky)
    return result_dict

def unweighted_analysis(llh, trial):
    ns = NeutrinoSample()
    ns.inputTrial(trial)
    llh.inputData(ns)
    result_dict = {}
    result_dict['f_fit'], result_dict['TS'] = llh.minimize__lnL()
    result_dict['n_fit'] = result_dict['f_fit'] * llh.Ncount
    result_dict['flux_fit'] = llh.event_generator.trial_runner.to_dNdE(result_dict['n_fit'], E0=1e5) / (4*np.pi*llh.f_sky)
    return result_dict

def template_analysis(trial, nexc, trial_runner):
    result = {}
    result['template_TS'], result['template_n_fit'] = trial_runner.get_one_fit_from_trial((trial, nexc))
    return result


if __name__ == '__main__':
    main()
