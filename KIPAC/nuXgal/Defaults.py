"""Default values for analysis parameters"""

import os

import numpy as np

import healpy as hp

VERBOSE = False

# Fixed parameters for the Neutrino sample
NSIDE = 128             # About 1 square degree pixels
LOG_EMIN = 2.5         # 1000 GeV
LOG_EMAX = 5.5          # 1e9 GeV
NEEdges = 4             # 4 edges, 3 bins, 1 bin per decade

DT_DAYS = 333           # Length of run1
DT_SECONDS = 28771200   # 333 * 86400
M2_TO_CM2 = 1e4         # Conversion for effective area



# Directories and file names
if 'NUXGAL_DIR' in os.environ:
    NUXGAL_DIR = os.environ['NUXGAL_DIR']
else:
    NUXGAL_DIR = os.path.dirname(__file__)
print("Using %s for NUXGAL_DIR" % NUXGAL_DIR)

# Directories
NUXGAL_ANCIL_DIR = os.path.join(NUXGAL_DIR, 'data', 'ancil')
NUXGAL_IRF_DIR = os.path.join(NUXGAL_DIR, 'data', 'irfs')
NUXGAL_DATA_DIR = os.path.join(NUXGAL_DIR, 'data', 'data')
NUXGAL_SYNTHETICDATA_DIR = os.path.join(NUXGAL_DIR, 'syntheticData')
NUXGAL_PLOT_DIR = os.path.join(NUXGAL_DIR, 'plots')
TESTFIG_DIR = os.path.join(NUXGAL_PLOT_DIR, 'test')
#NUXGAL_ANA_DIR = os.path.join(NUXGAL_DIR, 'data', 'ana')
#NUXGAL_ANA_ROOT = '/data/user/dguevel/nuXgal/ana'
NUXGAL_ANA_ROOT = os.path.join(NUXGAL_DIR, 'ana')
NUXGAL_TEMPLATE_ROOT = os.path.join(NUXGAL_ANA_ROOT, 'templates')
NUXGAL_ANA_DIR = os.path.join(NUXGAL_ANA_ROOT, '{nyear}_{galaxyName}_ebin{emin}-{emax}')
NUXGAL_TEMPLATE_DIR = os.path.join(NUXGAL_TEMPLATE_ROOT, '{nyear}_{galaxyName}_ebin{emin}-{emax}')
NUXGAL_ANA_FORMAT = os.path.join(NUXGAL_ANA_DIR, 'NT86v5.subanalysis.version-005-p01.npy')
NUXGAL_TEMPLATE_FORMAT = os.path.join(NUXGAL_TEMPLATE_DIR, 'NT86v5.template.npy')

# Format strings for file paths
NCOSTHETA_FORMAT = os.path.join(NUXGAL_IRF_DIR, 'Ncos_theta_{year}_{ebin}.txt')
WEIGHTED_AEFF_FORMAT = os.path.join(NUXGAL_IRF_DIR, 'WeightedAeff_{year}_{specIndex}_{ebin}.fits')
TABULATED_AEFF_FORMAT = os.path.join(NUXGAL_IRF_DIR, '{year}-TabulatedAeff.txt')
EXPOSUREMAP_FORMAT = os.path.join(NUXGAL_IRF_DIR, '{year}-ExposureMap.npy')
BEAM_FNAME_FORMAT = os.path.join(NUXGAL_IRF_DIR, 'beam_{year}_ebin{ebin}.npy')

ANALYTIC_CL_PATH = os.path.join(NUXGAL_ANCIL_DIR, 'Cl_ggRM.dat')
GALAXYMAP_FORMAT = os.path.join(NUXGAL_ANCIL_DIR, '{galaxyName}_galaxymap.fits')
GALAXYMAP_TRUE_FORMAT = os.path.join(NUXGAL_ANCIL_DIR, '{galaxyName}_galaxymap_true.fits')
GALAXYALM_FORMAT = os.path.join(NUXGAL_ANCIL_DIR, '{galaxyName}_overdensityalm.fits')
W_MEAN_FORMAT = os.path.join(NUXGAL_ANCIL_DIR, 'w_mean_{galaxyName}_{nyear}.npy')

GALAXYMAP_FIG_FORMAT =  os.path.join(NUXGAL_PLOT_DIR, 'test_{galaxyName}_galaxy.pdf')

SYNTHETIC_EVTMAP_ASTRO_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'eventmap_astro{i}.fits')
SYNTHETIC_EVTMAP_ATM_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'eventmap_atm{i}.fits')

SYNTHETIC_W_MEAN_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_mean_{galaxyName}_{nyear}_{method}_gamma{gamma}.npy')
SYNTHETIC_W_STD_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_std_{galaxyName}_{nyear}_{method}_gamma{gamma}.npy')
SYNTHETIC_ATM_CROSS_CORR_STD_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_atm_std_{galaxyName}_{nyear}.npy')
SYNTHETIC_ATM_NCOUNTS_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'Ncount_atm_after_masking_{galaxyName}_{nyear}.txt')
SYNTHETIC_ATM_W_MEAN_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_atm_mean_{galaxyName}_{nyear}.txt')
SYNTHETIC_ASTRO_W_MEAN_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_astro_mean_{galaxyName}_{nyear}.txt')
SYNTHETIC_ASTRO_W_STD_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_astro_std_{galaxyName}_{nyear}.txt')
SYNTHETIC_W_COV_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'w_cov_{galaxyName}_{nyear}.npy')

SYNTHETIC_TS_NULL_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'TS_{f_diff}_{galaxyName}_{nyear}.txt')
SYNTHETIC_TS_SIGNAL_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'TS_{f_diff}_{galaxyName}_{nyear}_{astroModel}.txt')

CORNER_PLOT_FORMAT = os.path.join(NUXGAL_SYNTHETICDATA_DIR, 'corner_{galaxyName}_{nyear}.h5')


# Other things
randomseed_galaxy = 42                                             # Seed used to produce random galaxy sample
THREE_YEAR_NAMES = ['IC79-2010', 'IC86-2011', 'IC86-2012']         # Keys for 3 year data sample
STANDARD_SPECTRAL_INDICES = [3.7, 2.28, 2.89]                      # Indices to use for weighted effective area and exposure maps


# Derived quantities for analyzing the Neutrino sample and cross-correlation

# Energy binning
NEbin = NEEdges-1                                                  # Number of Energy bins
map_logE_edge = np.linspace(LOG_EMIN, LOG_EMAX, NEEdges)           # log10(E/GeV) of energy bin edges
map_logE_center = (map_logE_edge[0:-1] + map_logE_edge[1:]) / 2.   # Energy bin centers in log10(E/GeV)
map_dlogE = np.mean(map_logE_edge[1:] - map_logE_edge[0:-1])       # Width of energy bins in log10(E/GeV)
map_E_edge = np.power(10, map_logE_edge)                           # Energy bin edges in GeV
map_E_center = np.power(10, map_logE_center)                       # Energy bin geometric centers
map_E_center_sq = map_E_center * map_E_center                      # Square of energy bin centers
#dlogE_micro=0.25                                               # log10(Energy) microbin size
dlogE_micro = 1.
logE_microbin_edge = np.arange(LOG_EMIN, LOG_EMAX + dlogE_micro, dlogE_micro)   # log10(Energy) microbin edges

# Sin dec bins
dsindec = 0.05                                                     # Sin declination bin size
#dsindec = 0.1
sindec_bin_edge = np.arange(-1, 1. + dsindec, dsindec)             # Sin declination bin edges

# Spatial binning and spherical harmonic parameters
NPIXEL = hp.pixelfunc.nside2npix(NSIDE)    # Number of pixels
NCL = 3*NSIDE                              # Number of c_l to use in analysis
NALM = int((NCL) * (NCL+1) / 2)            # Number of a_lm to use in analysis
MAX_L = NCL - 1                            # Largest L to use in analysis
ell = np.arange(NCL)                       # Array of all l values, useful in plotting

# southern sky mask
exposuremap_theta, exposuremap_phi = hp.pixelfunc.pix2ang(NSIDE, np.arange(NPIXEL))
theta_north = np.radians(95.)
#theta_north = np.radians(180.)
idx_muon = np.where(exposuremap_theta > theta_north)

GAMMAS = np.arange(1.5, 4.1, .5)
#ANALYSIS_VERSION = 'version-003-p03'
ANALYSIS_VERSION = 'version-004-p02'
#ANALYSIS_VERSION = 'version-001-p02'
