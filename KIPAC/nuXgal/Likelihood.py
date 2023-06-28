"""Defintion of Likelihood function"""

import os
import numpy as np
import healpy as hp
import emcee
import corner
import csky as cy
import json
import itertools
import warnings

from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib
from pandas import concat

from scipy.optimize import minimize
from scipy.stats import norm, distributions
from scipy.interpolate import interp1d

from .EventGenerator import EventGenerator
from . import Defaults
from .NeutrinoSample import NeutrinoSample
from .FermipyCastro import LnLFn
from .GalaxySample import GALAXY_LIBRARY
from .Exposure import ICECUBE_EXPOSURE_LIBRARY
from .CskyEventGenerator import CskyEventGenerator


def significance(chi_square, dof):
    """Construct an significance for a chi**2 distribution

    Parameters
    ----------
    chi_square : `float`
    dof : `int`

    Returns
    -------
    significance : `float`
    """
    p_value = distributions.chi2.sf(chi_square, dof)
    significance_twoTailNorm = norm.isf(p_value/2)
    return significance_twoTailNorm


def significance_from_chi(chi):
    """Construct an significance set of chi values

    Parameters
    ----------
    chi : `array`
    dof : `int`

    Returns
    -------
    significance : `float`
    """
    chi2 = chi*chi
    dof = len(chi2)
    return significance(np.sum(chi2), dof)


class Likelihood():
    """Class to evaluate the likelihood for a particular model of neutrino galaxy correlation"""
    BlurredGalaxyMapFname = Defaults.BLURRED_GALAXYMAP_FORMAT
    WMeanFname = Defaults.W_MEAN_FORMAT
    AtmSTDFname = Defaults.SYNTHETIC_ATM_CROSS_CORR_STD_FORMAT
    AtmNcountsFname = Defaults.SYNTHETIC_ATM_NCOUNTS_FORMAT
    AtmMeanFname = Defaults.SYNTHETIC_ATM_W_MEAN_FORMAT
    AstroMeanFname = Defaults.SYNTHETIC_ASTRO_W_MEAN_FORMAT
    AstroSTDFname = Defaults.SYNTHETIC_ASTRO_W_STD_FORMAT
    BeamFname = Defaults.BEAM_FORMAT
    IC_BEAM = '/Users/dguevel/git/nuXgal/data/ancil/IC_beam.npy'
    neutrino_sample_class = NeutrinoSample

    def __init__(self, N_yr, galaxyName, computeSTD, Ebinmin, Ebinmax, lmin, gamma=2.5):
        """C'tor

        Parameters
        ----------
        N_yr : `float`
            Number of years to simulate if computing the models
        galaxyName : `str`
            Name of the Galaxy sample
        computeSTD : `bool`
            If true, compute the standard deviation for a number of trials
        Ebinmin, Ebinmax : `int`
           indices of energy bins between which likelihood is computed
        lmin:
            minimum of l to be taken into account in likelihood
        """

        self.N_yr = N_yr
        self.gs = GALAXY_LIBRARY.get_sample(galaxyName)
        self.BlurredGalaxyMapFname = self.BlurredGalaxyMapFname.format(galaxyName=self.gs.galaxyName)
        self.AtmSTDFname = self.AtmSTDFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.AtmNcountsFname = self.AtmNcountsFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.AtmMeanFname = self.AtmMeanFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.WMeanFname =  self.WMeanFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.AstroMeanFname = self.AstroMeanFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.AstroSTDFname = self.AstroSTDFname.format(galaxyName=self.gs.galaxyName, nyear= str(self.N_yr))
        self.BeamFname = self.BeamFname.format(nyear=str(self.N_yr))
        self.anafastMask()
        self.Ebinmin = Ebinmin
        self.Ebinmax = Ebinmax
        self.lmin = lmin
        # scaled mean and std
        self.event_generator = CskyEventGenerator(self.N_yr, self.gs, gamma=gamma, Ebinmin=Ebinmin, Ebinmax=Ebinmax, idx_mask=self.idx_mask)
        self.calculate_w_mean()
        self.w_data = None
        self.Ncount = None
        self.gamma = gamma

        # compute or load w_atm distribution
        if computeSTD:
            self.computeAtmophericEventDistribution(N_re=5000, writeMap=True)
            self.computeAstrophysicalEventDistribution(N_re=5000, writeMap=True)
        else:
            w_atm_std_file = np.loadtxt(self.AtmSTDFname)
            self.w_atm_std = w_atm_std_file.reshape((Defaults.NEbin, Defaults.NCL))
            self.w_atm_std_square = self.w_atm_std ** 2
            w_atm_mean_file = np.loadtxt(self.AtmMeanFname)
            self.w_atm_mean = w_atm_mean_file.reshape((Defaults.NEbin, Defaults.NCL))
            self.Ncount_atm = np.loadtxt(self.AtmNcountsFname)
            self.Ncount_atm = self.Ncount_atm.reshape(Defaults.NEbin)

            w_astro_mean_file = np.loadtxt(self.AstroMeanFname)
            self.w_model_f1 = w_astro_mean_file.reshape((Defaults.NEbin, Defaults.NCL))
            w_astro_std_file = np.loadtxt(self.AstroSTDFname)
            self.w_model_f1_std = w_astro_std_file.reshape((Defaults.NEbin, Defaults.NCL))



    def anafastMask(self):
        """Generate a mask that merges the neutrino selection mask
        with the galaxy sample mask
        """
        # mask Southern sky to avoid muons
        mask_nu = np.zeros(Defaults.NPIXEL, dtype=np.bool)
        mask_nu[Defaults.idx_muon] = 1.
        # add the mask of galaxy sample
        mask_nu[self.gs.idx_galaxymask] = 1.
        self.idx_mask = np.where(mask_nu != 0)
        self.f_sky = 1. - len(self.idx_mask[0]) / float(Defaults.NPIXEL)

    def bootstrapSigma(self, ebin, niter=100):
        cl = np.zeros((niter, Defaults.NCL))
        evt = self.neutrino_sample.event_list
        elo, ehi = Defaults.map_logE_edge[ebin], Defaults.map_logE_edge[ebin + 1]
        flatevt = cy.utils.Events(concat([i.as_dataframe for i in itertools.chain.from_iterable(evt)]))
        flatevt = flatevt[(flatevt['log10energy'] >= elo) * (flatevt['log10energy'] < ehi)]
        for i in range(niter):
            ns2 = NeutrinoSample()
            idx = np.random.choice(len(flatevt), size=len(flatevt))
            newevt = flatevt[idx]

            ns2.inputTrial([[newevt]], 'v4')
            ns2.updateMask(self.idx_mask)
            # suppress invalid value warning which we get because of the energy bin filter
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                #cl[i] = ns2.getCrossCorrelation(self.gs.overdensityalm)[ebin]
                cl[i] = ns2.getCrossCorrelationEbin(self.gs.overdensityalm, ebin)

        return np.std(cl, axis=0)

    def loadSTDInterpolation(self):
        self.std_interps = {}
        self.std_interps_n = {}
        for ebin in range(Defaults.NEbin):
            with open('/home/dguevel/git/nuXgal/syntheticData/w_std_unWISE_z=0.4_v4_ebin{}.json'.format(ebin)) as fp:
                data = json.load(fp)

            self.std_interps[ebin] = interp1d(data['f_inj'], np.array([data['cl_std'][str(n)] for n in data['n_inj']]).T, fill_value='extrapolate', bounds_error=False)
            self.std_interps_n[ebin] = interp1d(data['n_inj'], np.array([data['cl_std'][str(n)] for n in data['n_inj']]).T, fill_value='extrapolate', bounds_error=False)


    def calculate_w_mean(self):
        """Compute the mean cross corrleations assuming neutrino sources follow the same alm
            Note that this is slightly different from the original Cl as the mask has been updated.
        """

        overdensity_g = hp.alm2map(self.gs.overdensityalm, nside=Defaults.NSIDE, verbose=False)
        overdensity_g[self.idx_mask] = hp.UNSEEN
        w_mean = hp.anafast(overdensity_g) / self.f_sky
        self.w_model_f1 = np.zeros((Defaults.NEbin, Defaults.NCL))
        for i in range(Defaults.NEbin):
            self.w_model_f1[i] = w_mean
        return

    def getPDFRatioWeight(self, *args):
        return 1.

    def computeAstrophysicalEventDistribution(self, N_re, writeMap):
        """Compute the cross correlation distribution for astrophysical events"""

        w_cross = np.zeros((N_re, Defaults.NEbin, 3 * Defaults.NSIDE))
        ns = self.neutrino_sample_class()
        eg = self.event_generator

        for iteration in tqdm(np.arange(N_re)):

            trial, nexc = eg.SyntheticTrial(1000000, self.idx_mask, signal_only=True)

            ns.inputTrial(trial, str(self.N_yr))
            ns.updateMask(self.idx_mask)
            self.inputData(ns, bootstrap_error=[])
            w_cross[iteration] = self.w_data.copy()

        self.w_model_f1 = np.mean(w_cross, axis=0)
        self.w_model_f1_std = np.std(w_cross, axis=0)

        if writeMap:
            np.savetxt(self.AstroMeanFname, self.w_model_f1)
            np.savetxt(self.AstroSTDFname, self.w_model_f1_std)



    def computeAtmophericEventDistribution(self, N_re, writeMap):
        """Compute the cross correlation distribution for Atmopheric event

        Parameters
        ----------
        N_re : `int`
           Number of realizations to use to compute the models
        writeMap : `bool`
           If true, save the distributions
        """

        w_cross = np.zeros((N_re, Defaults.NEbin, 3 * Defaults.NSIDE))
        Ncount_av = np.zeros(Defaults.NEbin)
        ns = self.neutrino_sample_class()
        eg = self.event_generator

        for iteration in tqdm(np.arange(N_re)):

            trial, nexc = eg.SyntheticTrial(0, self.idx_mask)
            ns.inputTrial(trial, str(self.N_yr))
            ns.updateFluxMap(gamma=self.gamma, ana=self.event_generator.ana)
            ns.updateCountsMap(gamma=self.gamma, ana=self.event_generator.ana)
            ns.updateMask(self.idx_mask)
            self.inputData(ns, bootstrap_error=[])
            w_cross[iteration] = self.w_data.copy()
            Ncount_av = Ncount_av + ns.getEventCounts()

        self.w_atm_mean = np.mean(w_cross, axis=0)
        self.w_atm_std = np.std(w_cross, axis=0)
        self.Ncount_atm = Ncount_av / float(N_re)
        self.w_atm_std_square = self.w_atm_std ** 2

        if writeMap:
            np.savetxt(self.AtmSTDFname, self.w_atm_std)
            np.savetxt(self.AtmNcountsFname, self.Ncount_atm)
            np.savetxt(self.AtmMeanFname, self.w_atm_mean)


    def inputData(self, ns, bootstrap_error=[]):
        """Input data

        Parameters
        ----------
        ns : `NeutrinoSample`
            A NeutrinoSample Object

        Returns
        -------
        None
        """

        self.neutrino_sample = ns
        ns.updateMask(self.idx_mask)
        self.w_data = ns.getCrossCorrelation(self.gs.overdensityalm)
        self.Ncount = ns.getEventCounts()

        # inputData can be called on Likelihood initialization if 
        # compute_std is True, before w_atm_std is defined
        if hasattr(self, 'w_atm_std'):
            self.w_std = np.copy(self.w_atm_std)
            self.w_std_square = np.copy(self.w_atm_std_square)
        else:
            self.w_std = np.zeros((Defaults.NEbin, Defaults.NCL))
            self.w_std_square = np.zeros((Defaults.NEbin, Defaults.NCL))

        for ebin in bootstrap_error:
            self.w_std[ebin] = self.bootstrapSigma(ebin)
            self.w_std_square[ebin] = self.w_std[ebin]**2


    def log_likelihood_Ebin(self, f, energyBin):
        """Compute the log of the likelihood for a particular model in given energy bin

        Parameters
        ----------
        f : `float`
            The fraction of neutrino events correlated with the Galaxy sample
        energyBin: `index`
            The energy bin where likelihood is computed
        Returns
        -------
        logL : `float`
            The log likelihood, computed as sum_l (data_l - f * model_mean_l) /  model_std_l
        """
        #w_model_mean = self.w_model_f1[energyBin] * f
        w_model_mean = (self.w_model_f1[energyBin].T * f)
        w_model_mean += (self.w_atm_mean[energyBin].T * (1 - f))
        #w_model_std_square = self.w_std_square0[energyBin] / self.Ncount[energyBin]
        w_model_std_square = self.w_std_square[energyBin]
        #w_model_std_square = self.std_interps[energyBin](f)**2

        lnL_le = - (self.w_data[energyBin] - w_model_mean) ** 2 / w_model_std_square / 2.
        return np.sum(lnL_le[self.lmin:])


    def log_likelihood(self, f):
        """Compute the log of the likelihood for a particular model

        Parameters
        ----------
        f : `float`
            The fraction of neutrino events correlated with the Galaxy sample

        Returns
        -------
        logL : `float`
            The log likelihood, computed as sum_l (data_l - f * model_mean_l) /  model_std_l
        """

        f = np.array(f)
        w_data = self.w_data

        w_model_mean = (self.w_model_f1[self.Ebinmin : self.Ebinmax].T * f).T
        w_model_mean += (self.w_atm_mean[self.Ebinmin : self.Ebinmax].T * (1 - f)).T

        w_model_std_square = (self.w_std[self.Ebinmin : self.Ebinmax].T)**2
        lnL_le = - (w_data[self.Ebinmin : self.Ebinmax] - w_model_mean) ** 2 / w_model_std_square.T / 2.


        return np.sum(lnL_le[:, self.lmin:])


    def chi_square_Ebin(self, f, energyBin):
        w_model_mean = (self.w_model_f1[energyBin].T * f)
        w_model_mean += (self.w_atm_mean[energyBin].T * (1 - f))
        w_model_std_square = self.w_std_square[energyBin]

        chisquare = (self.w_data[energyBin] - w_model_mean) ** 2 / w_model_std_square
        return np.sum(chisquare[self.lmin:])

    def minimize__lnL_analytic(self):
        len_f = self.Ebinmax - self.Ebinmin
        f = np.zeros(len_f)
        for i, ebin in enumerate(range(self.Ebinmin, self.Ebinmax)):
            cgg = self.w_model_f1[ebin, self.lmin:]
            cgnu = self.w_data[ebin, self.lmin:]
            cgatm = self.w_atm_mean[ebin, self.lmin:]
            cstd = self.w_std[ebin, self.lmin:]
            f[i] = np.sum((cgg-cgatm)*(cgnu-cgatm)/cstd**2)/np.sum((cgg-cgatm)**2/cstd**2)
            #sigma_fhat = np.sqrt(1/np.sum(((cgg-cgatm)**2)/2/cstd**2))

        ts = 2*(self.log_likelihood(f) - self.log_likelihood(np.zeros(len_f)))
        return f, ts


    def minimize__lnL(self):
        """Minimize the log-likelihood
        Parameters
        ----------
        f : `float`
            The fraction of neutrino events correlated with the Galaxy sample
        Returns
        -------
        x : `array`
            The parameters that minimize the log-likelihood
        TS : `float`
            The Test Statistic, computed as 2 * logL_x - logL_0
        """
        len_f = self.Ebinmax - self.Ebinmin
        nll = lambda *args: -self.log_likelihood(*args)
        initial = 0.1 + 0.1 * np.random.randn(len_f)
        soln = minimize(nll, initial, bounds=[(0, 1)] * (len_f))
        #soln = minimize(nll, initial)

        return soln.x, (self.log_likelihood(soln.x) -\
                            self.log_likelihood(np.zeros(len_f))) * 2

    def minimize__lnL_free_index(self):
        """Minimize the log-likelihood

        Parameters
        ----------
        f : `float`
            The fraction of neutrino events correlated with the Galaxy sample

        Returns
        -------
        x : `array`
            The parameters that minimize the log-likelihood
        TS : `float`
            The Test Statistic, computed as 2 * logL_x - logL_0
        """
        len_f = (self.Ebinmax - self.Ebinmin)
        nll = lambda *args: -self.log_likelihood(*args)
        initial = 0.5 + 0.1 * np.random.randn(len_f)
        initial = np.hstack([initial, [2.5]])
        bounds = len_f * [[-4, 4],] + [[Defaults.GAMMAS.min(), Defaults.GAMMAS.max()]]
        soln = minimize(nll, initial, bounds=bounds)
        null_x = len_f * [0] + [2.5]
        return soln.x, (self.log_likelihood(soln.x) -\
                            self.log_likelihood(null_x)) * 2


    def TS_distribution(self, N_re, f_diff, astroModel='observed_numu_fraction', writeData=True):
        """Generate a Test Statistic distribution for simulated trials

        Parameters
        ----------
        N_re : `int`
           Number of realizations to use
        f_diff : `float`
            Input value for signal fraction
        writeData : `bool`
            Write the TS distribution to a text file

        Returns
        -------
        TS_array : `np.array`
            The array of TS values
        """
        eg_2010 = EventGenerator('IC79-2010',   astroModel=astroModel)
        eg_2011 = EventGenerator('IC86-2011',   astroModel=astroModel)
        eg_2012 = EventGenerator('IC86-2012',   astroModel=astroModel)

        TS_array = np.zeros(N_re)
        for i in range(N_re):
            if self.N_yr != 3:
                datamap = eg_2010.SyntheticData(1., f_diff=f_diff, density_nu=self.gs.density) +\
                    eg_2011.SyntheticData((self.N_yr - 1.)/2., f_diff=f_diff, density_nu=self.gs.density) +\
                    eg_2012.SyntheticData((self.N_yr - 1.)/2., f_diff=f_diff, density_nu=self.gs.density)
            else:
                datamap = eg_2010.SyntheticData(1., f_diff=f_diff, density_nu=self.gs.density) +\
                    eg_2011.SyntheticData(1., f_diff=f_diff, density_nu=self.gs.density) +\
                    eg_2012.SyntheticData(1., f_diff=f_diff, density_nu=self.gs.density)
            ns = self.neutrino_sample_class()
            ns.inputCountsmap(datamap)
            #ns.plotCountsmap(os.path.join(Defaults.NUXGAL_PLOT_DIR, 'Figcheck'))
            self.inputData(ns)
            minimizeResult = (self.minimize__lnL())
            print(i, self.Ncount, minimizeResult[0], minimizeResult[-1])
            TS_array[i] = minimizeResult[-1]
        if writeData:
            if f_diff == 0:
                TSpath = Defaults.SYNTHETIC_TS_NULL_FORMAT.format(f_diff=str(f_diff),  galaxyName=self.gs.galaxyName,    nyear=str(self.N_yr))


            else:
                TSpath = Defaults.SYNTHETIC_TS_SIGNAL_FORMAT.format(f_diff=str(f_diff), galaxyName=self.gs.galaxyName, nyear=str(self.N_yr), astroModel=astroModel)

            np.savetxt(TSpath, TS_array)
        return TS_array



    def plotCastro(self, TS_threshold=4, coloralphalimit=0.01, colorfbin=500):
        """Make a 'Castro' plot of the likelihood

        Parameters
        ----------
        TS_threshold : `float`
            Theshold at which to cut off the colormap
        coloralphalimit : `float`
        colorfbin : `int`
        """
        plt.figure(figsize=(8, 6))
        font = {'family': 'Arial', 'weight' : 'normal', 'size'   : 21}
        legendfont = {'fontsize' : 21, 'frameon' : False}
        matplotlib.rc('font', **font)
        matplotlib.rc('legend', **legendfont)
        matplotlib.rc("text", usetex=True)

        plt.ylabel(r'$E^2 dN/dE\,[\mathrm{GeV\,cm^{-2}\,s^{-1}\,sr^{-1}}]$')
        plt.xlabel(r'$\log$ (E [GeV])')
        #plt.ylim(1e-3, 10) # for f_astro
        plt.ylim(1e-9, 1e-5) # for flux
        plt.xlim(2.5, 5.5)
        plt.yscale('log')

        #cmap = matplotlib.colors.LinearSegmentedColormap.from_list("",
        #["dimgrey", "olive", "forestgreen","yellowgreen"])
        #["white",  "dimgray",  "mediumslateblue",  "cyan", "yellow", "red"]
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list("", ["navy", "deepskyblue", "lightgrey"])


        bestfit_f, _ = self.minimize__lnL()

        # common x for castro object initialization
        f_Ebin = np.linspace(0, 4, 1000)

        exposuremap = ICECUBE_EXPOSURE_LIBRARY.get_exposure('IC86-2012', 2.28)

        for idx_E in range(self.Ebinmin, self.Ebinmax):
            # exposuremap assuming alpha = 2.28 (numu) to convert bestfit f_astro to flux
            exposuremap_E = exposuremap[idx_E].copy()
            exposuremap_E[self.idx_mask] = hp.UNSEEN
            exposuremap_E = hp.ma(exposuremap_E)
            factor_f2flux = self.Ncount[idx_E] / (exposuremap_E.mean() * 1e4 * Defaults.DT_SECONDS *
                                                  self.N_yr * 4 * np.pi * self.f_sky * Defaults.map_dlogE *
                                                  np.log(10.)) * Defaults.map_E_center[idx_E]

            idx_bestfit_f = idx_E - self.Ebinmin
            lnl_max = self.log_likelihood_Ebin(bestfit_f[idx_bestfit_f], idx_E)
            lnL_Ebin = np.zeros_like(f_Ebin)
            for idx_f, f in enumerate(f_Ebin):
                lnL_Ebin[idx_f] = self.log_likelihood_Ebin(f, idx_E)

            castro = LnLFn(f_Ebin, -lnL_Ebin)
            TS_Ebin = castro.TS()
            # if this bin is significant, plot the 1 sigma interval
            if TS_Ebin > TS_threshold:
                f_lo, f_hi = castro.getInterval(0.32)
                plt.errorbar(Defaults.map_logE_center[idx_E], bestfit_f[idx_bestfit_f] * factor_f2flux,
                             yerr=[[(bestfit_f[idx_bestfit_f]-f_lo) * factor_f2flux],
                                   [(f_hi-bestfit_f[idx_bestfit_f]) * factor_f2flux]],
                             xerr=Defaults.map_dlogE/2., color='k')
                f_select_lo, f_select_hi = castro.getInterval(coloralphalimit)

            # else plot the 2 sigma upper limit
            else:
                f_hi = castro.getLimit(0.05)
                #print (f_hi)
                plt.errorbar(Defaults.map_logE_center[idx_E], f_hi * factor_f2flux, yerr=f_hi * factor_f2flux * 0.2,
                             xerr=Defaults.map_dlogE/2., uplims=True, color='k')
                f_select_lo, f_select_hi = 0, castro.getLimit(coloralphalimit)


            # compute color blocks of delta likelihood
            dlnl = np.zeros((colorfbin, 1))
            f_select = np.linspace(f_select_lo, f_select_hi, colorfbin+1)

            for idx_f_select, _f_select in enumerate(f_select[:-1]):
                dlnl[idx_f_select][0] = self.log_likelihood_Ebin(_f_select, idx_E) - lnl_max

            y_select = f_select * factor_f2flux
            m = plt.pcolormesh([Defaults.map_logE_edge[idx_E], Defaults.map_logE_edge[idx_E+1]], y_select, dlnl,
                               cmap=cmap, vmin=-2.5, vmax=0., linewidths=0, edgecolors='none')

        cbar = plt.colorbar(m)
        cbar.ax.set_ylabel(r'$\Delta\log\,L$', rotation=90, fontsize=16, labelpad=15)
        plt.subplots_adjust(left=0.14, bottom=0.14)
        plt.savefig(os.path.join(Defaults.NUXGAL_PLOT_DIR, 'Fig_sedlnl.png'))





    def log_prior(self, f):
        """Compute log of the prior on a f, implemented as a flat prior between 0 and 1.5

        Parameters
        ----------
        f : `float`
            The signal fraction

        Returns
        -------
        value : `float`
            The log of the prior
        """
        if np.min(f) > -4. and np.max(f) < 4.:
            return 0.
        return -np.inf


    def log_probability(self, f):
        """Compute log of the probablity of f, given some data

        Parameters
        ----------
        f : `float`
            The signal fraction

        Returns
        -------
        value : `float`
            The log of the probability, defined as log_prior + log_likelihood
        """
        lp = self.log_prior(f)
        if not np.isfinite(lp):
            return -np.inf
        return lp + self.log_likelihood(f)




    def runMCMC(self, Nwalker, Nstep):
        """Run a Markov Chain Monte Carlo

        Parameters
        ----------
        Nwalker : `int`
        Nstep : `int`
        """

        ndim = self.Ebinmax - self.Ebinmin
        pos = 0.3 + np.random.randn(Nwalker, ndim) * 0.1
        nwalkers, ndim = pos.shape
        backend = emcee.backends.HDFBackend(Defaults.CORNER_PLOT_FORMAT.format(galaxyName=self.gs.galaxyName,
                                                                               nyear=str(self.N_yr)))
        backend.reset(nwalkers, ndim)
        sampler = emcee.EnsembleSampler(nwalkers, ndim, self.log_probability, backend=backend)
        sampler.run_mcmc(pos, Nstep, progress=True)



    def plotMCMCchain(self, ndim, labels, truths, plotChain=False):
        """Plot the results of a Markov Chain Monte Carlo

        Parameters
        ----------
        ndim : `int`
            The number of variables
        labels : `array`
            Labels for the variables
        truths : `array`
            The MC truth values
        """

        reader = emcee.backends.HDFBackend(Defaults.CORNER_PLOT_FORMAT.format(galaxyName=self.gs.galaxyName,
                                                                              nyear=str(self.N_yr)))
        if plotChain:
            fig, axes = plt.subplots(ndim, figsize=(10, 7), sharex=True)
            samples = reader.get_chain()

            for i in range(ndim):
                ax = axes[i]
                ax.plot(samples[:, :, i], "k", alpha=0.3)
                ax.set_xlim(0, len(samples))
                ax.set_ylabel(labels[i])
                ax.yaxis.set_label_coords(-0.1, 0.5)

            axes[-1].set_xlabel("step number")
            fig.savefig(os.path.join(Defaults.NUXGAL_PLOT_DIR, 'MCMCchain.pdf'))

        flat_samples = reader.get_chain(discard=100, thin=15, flat=True)
        #print(flat_samples.shape)
        fig = corner.corner(flat_samples, labels=labels, truths=truths)
        fig.savefig(os.path.join(Defaults.NUXGAL_PLOT_DIR, 'Fig_MCMCcorner.pdf'))
