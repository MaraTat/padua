__author__ = 'mfitzp'

import pandas as pd
import numpy as np
import scipy as sp

from collections import defaultdict
import re
import itertools
from .utils import qvalues

import matplotlib
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from matplotlib import gridspec

from statsmodels.stats.multitest import multipletests
import warnings   


import matplotlib.gridspec as gridspec
from matplotlib.colors import colorConverter
from matplotlib.backends.backend_agg import FigureCanvasAgg
import scipy.spatial.distance as distance
import scipy.cluster.hierarchy as sch
import matplotlib.cm as cm
import matplotlib.image as mplimg


from matplotlib.patches import Ellipse

from io import BytesIO, StringIO

"""
Visualization tools for proteomic data, using standard Pandas dataframe structures
from imported data. These functions make some assumptions about the structure of
data, but generally try to accomodate.

Depends on scikit-learn for PCA analysis
"""

from . import analysis
from . import process


def get_protein_id(s):
    """
    Return a shortened string, split on spaces, underlines and semicolons.

    Extract the first, highest-ranked protein ID from a string containing
    protein IDs in MaxQuant output format: e.g. P07830;P63267;Q54A44;P63268

    Long names (containing species information) are eliminated (split on ' ') and
    isoforms are removed (split on '_').

    :param s:  protein IDs in MaxQuant format
    :type s: str or unicode
    :return: string
    """
    return s.split(';')[0].split(' ')[0].split('_')[0]


def get_protein_ids(s):
    """
    Return a list of shortform protein IDs.

    Extract all protein IDs from a string containing
    protein IDs in MaxQuant output format: e.g. P07830;P63267;Q54A44;P63268

    Long names (containing species information) are eliminated (split on ' ') and
    isoforms are removed (split on '_').

    :param s:  protein IDs in MaxQuant format
    :type s: str or unicode
    :return: list of string ids
    """
    return [p.split(' ')[0].split('_')[0]  for p in s.split(';') ]

   
def get_protein_id_list(df, level=0):
    """
    Return a complete list of shortform IDs from a DataFrame

    Extract all protein IDs from a dataframe from multiple rows containing
    protein IDs in MaxQuant output format: e.g. P07830;P63267;Q54A44;P63268

    Long names (containing species information) are eliminated (split on ' ') and
    isoforms are removed (split on '_').

    :param df: DataFrame
    :type df: pandas.DataFrame
    :param level: Level of DataFrame index to extract IDs from
    :type level: int or str
    :return: list of string ids
    """
    protein_list = []
    for s in df.index.get_level_values(level):
        protein_list.extend( get_protein_ids(s) )
 
    return list(set(protein_list))    


def get_shortstr(s):
    """
    Return the first part of a string before a semicolon.

    Extract the first, highest-ranked protein ID from a string containing
    protein IDs in MaxQuant output format: e.g. P07830;P63267;Q54A44;P63268

    :param s:  protein IDs in MaxQuant format
    :type s: str or unicode
    :return: string
    """
    return str(s).split(';')[0]


def get_index_list(l, ms):
    if type(ms) != list and type(ms) != tuple:
        ms = [ms]
    return [l.index(s) for s in ms if s in l]


def build_combined_label(sl, idxs, sep=' '):
    """
    Generate a combined label from a list of indexes
    into sl, by joining them with `sep` (str).

    :param sl: Strings to combine
    :type sl: dict of str
    :param idxs: Indexes into sl
    :type idxs: list of sl keys
    :param sep:

    :return: `str` of combined label
    """
    return sep.join([get_shortstr(str(sl[n])) for n in idxs])


def hierarchical_match(d, k, default=None):
    """
    Match a key against a dict, simplifying element at a time


    :param df: DataFrame
    :type df: pandas.DataFrame
    :param level: Level of DataFrame index to extract IDs from
    :type level: int or str
    :return: hiearchically matched value or default
    """
    if d is None:
        return default

    if type(k) != list and type(k) != tuple:
        k = [k]

    for n, _ in enumerate(k):
        key = tuple(k[0:len(k)-n])
        if len(key) == 1:
            key = key[0]

        try:
            d[key]
        except:
            pass
        else:
            return d[key]
    return default


def chunks(seq, num):
    """
    Separate `seq` (`np.array`) into `num` series of as-near-as possible equal
    length values.

    :param seq: Sequence to split
    :type seq: np.array
    :param num: Number of parts to split sequence into
    :type num: int
    :return: np.array of split parts
    """

    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return np.array(out)
 
    
def calculate_s0_curve(s0, minpval, maxpval, minratio, maxratio, curve_interval=0.1):

    #maxpval, minpval  = np.nanmin(p), np.nanmax(p)
    #minratio, maxratio = np.nanmin(ratio), np.nanmax(ratio)

    mminpval = -np.log10(minpval)
    mmaxpval = -np.log10(maxpval)
    maxpval_adjust = mmaxpval - mminpval

    ax0 = (s0 + maxpval_adjust * minratio) / maxpval_adjust
    edge_offset = (maxratio-ax0) % curve_interval
    max_x = maxratio-edge_offset
    

    if (max_x > ax0):
        x = np.arange(ax0, max_x, curve_interval)
    else:
        x = np.arange(max_x, ax0, curve_interval)

    fn = lambda x: 10 ** (-s0/(x-minratio) - mminpval)
    y = fn(x)
    
    return x, y, fn    



# Add ellipses for confidence intervals, with thanks to Joe Kington
# http://stackoverflow.com/questions/12301071/multidimensional-confidence-intervals
def plot_point_cov(points, nstd=2, **kwargs):
    """
    Plots an `nstd` sigma ellipse based on the mean and covariance of a point
    "cloud" (points, an Nx2 array).

    Parameters
    ----------
        points : An Nx2 array of the data points.
        nstd : The radius of the ellipse in numbers of standard deviations.
            Defaults to 2 standard deviations.
        Additional keyword arguments are pass on to the ellipse patch.

    Returns
    -------
        A matplotlib ellipse artist
    """
    pos = points.mean(axis=0)
    cov = np.cov(points, rowvar=False)
    return plot_cov_ellipse(cov, pos, nstd, **kwargs)


def plot_cov_ellipse(cov, pos, nstd=2, **kwargs):
    """
    Plots an `nstd` sigma error ellipse based on the specified covariance
    matrix (`cov`). Additional keyword arguments are passed on to the
    ellipse patch artist.

    Parameters
    ----------
        cov : The 2x2 covariance matrix to base the ellipse on
        pos : The location of the center of the ellipse. Expects a 2-element
            sequence of [x0, y0].
        nstd : The radius of the ellipse in numbers of standard deviations.
            Defaults to 2 standard deviations.
        Additional keyword arguments are pass on to the ellipse patch.

    Returns
    -------
        A matplotlib ellipse artist
    """

    def eigsorted(cov):
        vals, vecs = np.linalg.eigh(cov)
        order = vals.argsort()[::-1]
        return vals[order], vecs[:, order]

    vals, vecs = eigsorted(cov)
    theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))

    # Width and height are "full" widths, not radius
    width, height = 2 * nstd * np.sqrt(vals)
    ellip = Ellipse(xy=pos, width=width, height=height, angle=theta, fill=False, **kwargs)

    return ellip



def _pca_scores(scores, pc1=0, pc2=1, fcol=None, ecol=None, marker='o', markersize=30, label_scores=None, show_covariance_ellipse=True, **kwargs):

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(1,1,1)
    levels = [0,1]    


    for c in set(scores.columns.get_level_values('Group')):

        try:
            data = scores[c].values.reshape(2,-1)
        except:
            continue

        fc = hierarchical_match(fcol, c, 'k')
        ec = hierarchical_match(ecol, c)
        
        if ec is None:
            ec = fc

        if type(markersize) == str:
            # Use as a key vs. index value in this levels
            idx = scores.columns.names.index(markersize)
            s = c[idx]
        elif callable(markersize):
            s = markersize(c)
        else:
            s = markersize

        ax.scatter(data[pc1,:], data[pc2,:], s=s, marker=marker, edgecolors=ec, c=fc)

        if show_covariance_ellipse and data.shape[1] > 2:
            cov = data[[pc1, pc2], :].T
            ellip = plot_point_cov(cov, nstd=2, linestyle='dashed', linewidth=0.5, edgecolor=ec or fc,
                                   alpha=0.8)  #**kwargs for ellipse styling
            ax.add_artist(ellip)

    if label_scores:
        scores_f = scores.iloc[ [pc1, pc2] ]
        idxs = get_index_list( scores_f.columns.names, label_scores )

        for n, (x, y) in enumerate(scores_f.T.values):
            r, ha = (30, 'left')
            ax.text(x, y, build_combined_label( scores_f.columns.values[n], idxs), rotation=r, ha=ha, va='baseline', rotation_mode='anchor', bbox=dict(boxstyle='round,pad=0.3', fc='#ffffff', ec='none', alpha=0.6))

        
    ax.set_xlabel(scores.index[pc1], fontsize=16)
    ax.set_ylabel(scores.index[pc2], fontsize=16)
    fig.tight_layout()
    return ax


def _pca_weights(weights, pc, threshold=None, label_threshold=None, label_weights=None, **kwargs):
    
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(1,1,1)
    ax.plot(weights.iloc[:, pc])
    ylim = np.max( np.abs( weights.values ) ) * 1.1
    ax.set_ylim( -ylim, +ylim  )
    ax.set_xlim(0, weights.shape[0])
    ax.set_aspect(1./ax.get_data_ratio())
    
    wts = weights.iloc[:, pc]

    if threshold:
        if label_threshold is None:
            label_threshold = threshold

        if label_weights:

            FILTER_UP = wts.values >= label_threshold
            FILTER_DOWN = wts.values <= -label_threshold
            FILTER = FILTER_UP | FILTER_DOWN

            wti = np.arange(0, weights.shape[0])
            wti = wti[FILTER]

            idxs = get_index_list( wts.index.names, label_weights )
            for x in wti:
                y = wts.iloc[x]
                r, ha =  (30, 'left') if y >= 0 else (-30, 'left')
                ax.text(x, y, build_combined_label( wts.index.values[x], idxs), rotation=r, ha=ha, va='baseline', rotation_mode='anchor', bbox=dict(boxstyle='round,pad=0.3', fc='#ffffff', ec='none', alpha=0.4))

        ax.axhline(threshold, 0, 1)
        ax.axhline(-threshold, 0, 1)

    ax.set_ylabel("Weights on Principal Component %d" % (pc+1), fontsize=16)
    fig.tight_layout()
    return ax
    

def pca(df, n_components=2, mean_center=False, fcol=None, ecol=None, marker='o', markersize=40, threshold=None, label_threshold=None, label_weights=None, label_scores=None, return_df=False, show_covariance_ellipse=False, *args, **kwargs):
    """
    Perform Principal Component Analysis (PCA) from input DataFrame and generate scores and weights plots.




    Note: the PCA is calculated using `analysis.pca` and will give identical results.


    :param df:
    :param n_components:
    :param mean_center:
    :param fcol:
    :param ecol:
    :param marker:
    :param markersize:
    :param threshold:
    :param label_threshold:
    :param label_weights:
    :param label_scores:
    :param return_df:
    :param show_covariance_ellipse:
    :param args:
    :param kwargs:
    :return:
    """

    scores, weights = analysis.pca(df, n_components=n_components, *args, **kwargs)

    scores_ax = _pca_scores(scores, fcol=fcol, ecol=ecol, marker=marker, markersize=markersize, label_scores=label_scores, show_covariance_ellipse=show_covariance_ellipse)
    weights_ax = []
    
    for pc in range(0, weights.shape[1]):
        weights_ax.append( _pca_weights(weights, pc, threshold=threshold, label_threshold=label_threshold, label_weights=label_weights) )
    
    if return_df:
        return scores, weights
    else:
        return scores_ax, weights_ax

    
def enrichment(df):
    """

    :param df:
    :return:
    """

    result = analysis.enrichment(df)

    axes = result.plot(kind='pie', subplots=True, figsize=(result.shape[1]*4, 3))
    for n, ax in enumerate(axes):
        #ax.legend().set_visible(False)
        total = result.values[1,n] + result.values[0,n]
        ax.annotate("%.1f%%" % (100 * result.values[0,n]/total), 
                 xy=(0.3, 0.6),  
                 xycoords='axes fraction',
                 color='w',
                 size=22)
        ax.set_xlabel( ax.get_ylabel(), fontsize=22)
        ax.set_ylabel("")
        ax.set_aspect('equal', 'datalim')

    return axes


def volcano(df, a, b=None, fdr=0.05, threshold=2, minimum_sample_n=0, estimate_qvalues=False, labels_from=None, labels_for=None, title=None, markersize=64, s0=0.00001, draw_fdr=True, is_log2=False, fillna=None, label_sig_only=True, ax=None, fc='grey'):
    """
    Volcano plot of two sample groups showing t-test p value vs. log2(fc).

    Generates a volcano plot for two sample groups, selected from `df` using `a` and `b` indexers. The mean of
    each group is calculated along the y-axis (per protein) and used to generate a log2 ratio. If a log2-transformed
    dataset is supplied set `islog2=True` (a warning will be given when negative values are present).

    A two-sample independent t-test is performed between each group. If `minimum_sample_n` is supplied, any values (proteins)
    without this number of samples will be dropped from the analysis.

    Individual data points can be labelled in the resulting plot by passing `labels_from` with a index name, and `labels_for`
    with a list of matching values for which to plot labels.


    :param df: Pandas `dataframe`
    :param a: `tuple` or `str` indexer for group A
    :param b: `tuple` or `str` indexer for group B
    :param fdr: `float` false discovery rate cut-off
    :param threshold: `float` log2(fc) ratio cut -off
    :param minimum_sample_n: `int` minimum sample for t-test
    :param estimate_qvalues: `bool` estimate Q values (adjusted P)
    :param labels_from: `str` or `int` index level to get labels from
    :param labels_for: `list` of `str` matching labels to show
    :param title: `str` title for plot
    :param markersize: `int` size of markers
    :param s0: `float` smoothing factor between fdr/fc cutoff
    :param draw_fdr: `bool` draw the fdr/fc curve
    :param is_log2: `bool` is the data log2 transformed already?
    :param fillna: `float` fill NaN values with value (default: 0)
    :param label_sig_only: `bool` only label significant values
    :param ax: matplotlib `axis` on which to draw
    :param fc: `str` hex or matplotlib color code, default color of points
    :return:
    """
    df = df.copy()
    
    if np.any(df.values < 0) and not is_log2:
        warnings.warn("Input data has negative values. If data is log2 transformed, set is_log2=True.")

    if fillna:
        df = df.fillna(fillna)
        
    if labels_from is None:
        labels_from = list(df.index.names)


    if b is not None:
        # Calculate ratio between two groups
        g1, g2 = df[a].values, df[b].values

        if is_log2:
            dr = np.nanmean(g2, axis=1) - np.nanmean(g1, axis=1)
        else:
            dr = np.log2(np.nanmean(g2, axis=1) / np.nanmean(g1, axis=1))

        ginv = ( (~np.isnan(g1)).sum(axis=1) < minimum_sample_n ) | ((~np.isnan(g2)).sum(axis=1) < minimum_sample_n)

        g1 = np.ma.masked_where(np.isnan(g1), g1)
        g2 = np.ma.masked_where(np.isnan(g2), g2)

        # Calculate the p value between two groups (t-test)
        t, p = sp.stats.mstats.ttest_ind(g1.T, g2.T)

    else:
        g1 = df[a].values
        dr = np.nanmean(g1, axis=1)

        ginv = (~np.isnan(g1)).sum(axis=1) < minimum_sample_n

        # Calculate the p value one sample t
        g1 = np.ma.masked_where(np.isnan(g1), g1)
        t, p = sp.stats.mstats.ttest_1samp(g1.T, popmean=0)

    p = np.array(p) # Unmask

    # Set p values to nan where not >= minimum_sample_n values
    p[ ginv ] = np.nan

    if ax is None:
        fig = plt.figure()
        fig.set_size_inches(10,10)

        ax = fig.add_subplot(1,1,1)

    if estimate_qvalues:
        p[~np.isnan(p)] = qvalues(p[~np.isnan(p)])
        ax.set_ylabel('-log$_{10}$(Q)')
    else:
        ax.set_ylabel('-log$_{10}$(p)')


    # There are values below the fdr
    s0x, s0y, s0fn = calculate_s0_curve(s0, fdr, min(fdr/2, np.nanmin(p)), np.log2(threshold), np.nanmax(np.abs(dr)), curve_interval=0.001)

    if draw_fdr is True:
        ax.plot(s0x, -np.log10(s0y), 'r', lw=1 )
        ax.plot(-s0x, -np.log10(s0y), 'r', lw=1 )

    # Select data based on s0 curve
    _FILTER_IN = []

    for x, y in zip(dr, p):
        x = np.abs(x)
        spy = s0fn(x)

        if len(s0x) == 0 or x < np.min(s0x):
            _FILTER_IN.append(False)
            continue

        if y <= spy:
            _FILTER_IN.append(True)
        else:
            _FILTER_IN.append(False)

    _FILTER_IN = np.array(_FILTER_IN)
    _FILTER_OUT = ~ _FILTER_IN
    

    def scatter(ax, f, c, alpha=0.5):
        # lw = [float(l[0][-1])/5 for l in df[ f].index.values]
        
        if type(markersize) == str:
            # Use as a key vs. index value in this levels
            s = df.index.get_level_values(markersize)
        elif callable(markersize):
            s = np.array([markersize(c) for c in df.index.values])
        else:
            s = np.ones((df.shape[0],))*markersize
        
        
        ax.scatter(dr[f], -np.log10(p[f]), c=c, s=s[f], linewidths=0, alpha=0.5)
    
    _FILTER_OUT1 = _FILTER_OUT & ~np.isnan(p) & (np.array(p) > fdr)
    scatter(ax, _FILTER_OUT1, fc, alpha=0.3)

    _FILTER_OUT1 = _FILTER_OUT & (np.array(p) <= fdr)
    scatter(ax, _FILTER_OUT1, 'blue', alpha=0.3)

    if labels_for:
        idxs = get_index_list( df.index.names, labels_from )
        for shown, label, x, y in zip( _FILTER_IN , df.index.values, dr, -np.log10(p)):
            
            if shown or not label_sig_only:
                label = build_combined_label( label, idxs)
                
                if labels_for == True or any([l in label for l in labels_for]):
                    r, ha, ofx, ofy =  (30, 'left', 0.15, 0.02) if x >= 0 else (-30, 'right', -0.15, 0.02)
                    t = ax.text(x+ofx, y+ofy, label , rotation=r, ha=ha, va='baseline', rotation_mode='anchor', bbox=dict(boxstyle='round,pad=0.3', fc='#ffffff', ec='none', alpha=0.4))

    scatter(ax, _FILTER_IN, 'red')
    

    ax.set_xlabel('log$_2$ ratio')

    
    # Centre the plot horizontally
    xmin, xmax = ax.get_xlim()
    xlim = np.max(np.abs([xmin, xmax]))
    ax.set_xlim((-xlim, xlim))
    _, ymax = ax.get_ylim()
    ax.set_ylim((0, ymax))

    if title:
        ax.set_title(title)
    
    return ax, p, dr, _FILTER_IN
    

def _bartoplabel(ax, name, mx, offset):
    # attach some text labels
    for ii,container in enumerate(ax.containers):
        rect = container.patches[0]
        height = rect.get_height()
        rect.set_width( rect.get_width() - 0.05 )
        ax.text(rect.get_x()+rect.get_width()/2., height+150, '%.2f%%'% (name[ii]/mx),
                ha='center', va='bottom', fontsize=15)
    
    
def modifiedaminoacids(df, kind='pie'):
    """



    :param df:
    :param kind:
    :return:
    """
    colors =   ['#6baed6','#c6dbef','#bdbdbd']
    total_aas, quants = analysis.modifiedaminoacids(df)
    
    df = pd.DataFrame()
    for a, n in quants.items():
        df[a] = [n]
    df.sort(axis=1, inplace=True)
    
    if kind == 'bar' or kind == 'both':
        ax1 = df.plot(kind='bar', figsize=(7,7), color=colors)
        ax1.set_ylabel('Number of phosphorylated amino acids')
        ax1.set_xlabel('Amino acid')
        ax1.set_xticks([])
        ylim = np.max(df.values)+1000
        ax1.set_ylim(0, ylim )
        _bartoplabel(ax1, 100*df.values[0], total_aas, ylim )

        ax1.set_xlim((-0.3, 0.3))
        return ax
    
    if kind == 'pie' or kind == 'both':

        dfp =df.T
        residues = dfp.index.values
        
        dfp.index = ["%.2f%% (%d)" % (100*df[i].values[0]/total_aas, df[i].values[0]) for i in dfp.index.values ]
        ax2 = dfp.plot(kind='pie', y=0, colors=colors)
        ax2.legend(residues, loc='upper left', bbox_to_anchor=(1.0, 1.0))
        ax2.set_ylabel('')
        ax2.set_xlabel('')
        ax2.figure.set_size_inches(6,6)

        for t in ax2.texts:
            t.set_fontsize(15)

        return ax2

    return ax1, ax2
    
    
def modificationlocalization(df):
    """



    :param df:
    :return:
    """
    colors =  ["#78c679", "#d9f0a3", "#ffffe5"]

    lp = df['Localization prob'].values
    class_i = np.sum(lp > 0.75)
    class_ii = np.sum( (lp > 0.5) & (lp <= 0.75 ) )
    class_iii = np.sum( (lp > 0.25) & (lp <= 0.5 ) )

    cl = [class_i, class_ii, class_iii]
    total_v = class_i + class_ii + class_iii
    
    df = pd.DataFrame(cl)

    df.index = ["%.2f%% (%d)" % (100*v/total_v, v) for n, v in enumerate(cl) ]
    
    ax = df.plot(kind='pie', y=0, colors=colors)

    ax.legend(['Class I (> 0.75)', 'Class II (> 0.5 ≤ 0.75)', 'Class III (> 0.25, ≤ 0.5)'],
              loc='upper left', bbox_to_anchor=(1.0, 1.0))
    ax.set_ylabel('')
    ax.set_xlabel('')

    for t in ax.texts:
        t.set_fontsize(15)

    ax.figure.set_size_inches(6,6)

    return ax
    
    
def box(df, s=None, title_from=None, subplots=False, figsize=(18,6), groups=None, fcol=None, ecol=None, hatch=None, ylabel="", xlabel=""):
    """


    :param df:
    :param s:
    :param title_from:
    :param subplots:
    :param figsize:
    :param groups:
    :param fcol:
    :param ecol:
    :param hatch:
    :param ylabel:
    :param xlabel:
    :return:
    """
    df = df.copy()

        
    if type(s) == str:
        s = [s]

    if title_from is None:
        title_from = list(df.index.names)

    # Build the combined name/info string using label_from; replace the index
    title_idxs = get_index_list( df.index.names, title_from )
    df.index = [build_combined_label(r, title_idxs) for r in df.index.values]
    
    if s:
        # Filter the table on the match string (s)
        df = df.iloc[ [all([str(si) in l for si in s]) for l in df.index.values] ]
    
    figures = []
    # Iterate each matching row, building the correct structure dataframe
    for ix in range(df.shape[0]):
        
        dfi = pd.DataFrame(df.iloc[ix]).T
        label = dfi.index.values[0]
        dfi = process.fold_columns_to_rows(dfi, levels_from=len(df.columns.names)-1)

        if subplots:
            gs = gridspec.GridSpec(1, len(subplots), width_ratios=[dfi[sp].shape[1] for sp in subplots])
            subplotl = subplots
        elif isinstance(dfi.columns, pd.MultiIndex) and len(dfi.columns.levels) > 1:
            subplotl = dfi.columns.levels[0]
            gs = gridspec.GridSpec(1, len(subplotl), width_ratios=[dfi[sp].shape[1] for sp in subplotl])
        else:
            # Subplots
            subplotl = [None]
            gs =  gridspec.GridSpec(1, 1) 


        first_ax = None

        fig = plt.figure(figsize=figsize)

        for n, sp in enumerate(subplotl):

            if sp is None:
                dfp = dfi
            else:
                dfp = dfi[sp]

            ax = fig.add_subplot(gs[n], sharey=first_ax)

            medians = dfp.median(axis=1, level=0).reset_index().set_index('Replicate') #.dropna(axis=1)

            if groups and all([g in medians.columns.get_level_values(0)]):
                medians = medians[ groups ]

            ax, dic = medians.plot(
                kind='box', 
                return_type = 'both',
                patch_artist=True,
                ax = ax,
            )

            ax.set_xlabel('')
            for n, c in enumerate(medians.columns.values):
                if sp is None:
                    hier = []
                else:
                    hier = [sp]  
                if type(c) == tuple:
                    hier.extend(c)
                else:
                    hier.append(c)
                    
                if fcol:
                    color = hierarchical_match(fcol, hier, None)
                    if color:
                        dic['boxes'][n].set_color( color )
                if ecol:
                    color = hierarchical_match(ecol, hier, None)
                    if color:
                        dic['boxes'][n].set_edgecolor( color )
                if hatch:
                    dic['boxes'][n].set_hatch( hierarchical_match(hatch, hier, '') )

            ax.set_xlabel(xlabel)
            ax.tick_params(axis='both', which='major', labelsize=12)

            if first_ax is None:
                first_ax = ax
            else:
                for yl in ax.get_yticklabels():
                    yl.set_visible(False)

        first_ax.set_ylabel(ylabel, fontsize=14)
        fig.subplots_adjust(wspace=0.05)

        fig.suptitle(label)
        
        figures.append(fig)
        
    return figures

    
def column_correlations(df, cmap=cm.Reds):
    """

    :param df:
    :param cmap:
    :return:
    """
    df = df.copy()
    df = df.astype(float)
    
    dfc = analysis.column_correlations(df)
    dfc = dfc.values

    # Plot the distributions
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    fig = plt.figure()
    fig.set_size_inches(12, 12)
    ax = fig.add_subplot(1,1,1)

    #vmax = np.max(dfc)
    #vmin = np.min(dfc)

    i = ax.imshow(dfc, cmap=cmap, vmin=0.5, vmax=1.0, interpolation='none')
    ax.figure.colorbar(i)
    ax.set_xticks([])
    ax.set_yticks([])
    
    return ax
    
    
def _process_ix(i, idx):
    if idx is None:
        return set(i)
        
    if len(idx) > 1:
        return set( zip([i.get_level_values(l) for l in idx]) )
    else:
        return set( i.get_level_values(idx[0]) )
        
    
def venn(df1, df2, df3=None, labels=None, ix1=None, ix2=None, ix3=None, return_intersection=False, fcols=None):
    """
    Plot a 2 or 3-part venn diagram showing the overlap between 2 or 3 pandas DataFrames.

    :param df1:
    :param df2:
    :param df3:
    :param labels:
    :param ix1:
    :param ix2:
    :param ix3:
    :param return_intersection:
    :param fcols:
    :return:
    """
    try:
        import matplotlib_venn as mplv
    except:
        ImportError("To plot venn diagrams, install matplotlib-venn package: pip install matplotlib-venn")
    
    if labels is None:
        labels = ["A", "B", "C"]
        
    s1 = _process_ix(df1.index, ix1)
    s2 = _process_ix(df2.index, ix2)
    if df3 is not None:
        s3 = _process_ix(df3.index, ix3)

    kwargs = {}

    if fcols:
        kwargs['set_colors'] = [fcols[l] for l in labels]

    if df3 is not None:
        vn = mplv.venn3([s1,s2,s3], set_labels=labels, **kwargs)
        intersection = s1 & s2 & s3
    else:
        vn = mplv.venn2([s1,s2], set_labels=labels, **kwargs)
        intersection = s1 & s2



    ax = plt.gca()

    if return_intersection:
        return ax, intersection
    else:
        return ax

        
def sitespeptidesproteins(df, labels=None, colors=None, site_localization_probability=0.75):
    """
    Plot the number of sites, peptides and proteins in the dataset.

    Generates a plot with sites, peptides and proteins displayed hierarchically in chevrons.
    The site count is limited to Class I (<=0.75 site localization probability) by default
    but may be altered using the `site_localization_probability` parameter.

    Labels and alternate colours may be supplied as a 3-entry iterable.

    :param df: pandas DataFrame to calculate numbers from
    :param labels: list/tuple of 3 strings containing labels
    :param colors: list/tuple of 3 colours as hex codes or matplotlib color codes
    :param site_localization_probability: the cut-off for site inclusion (default=0.75; Class I)
    :return:
    """
    fig = plt.figure(figsize=(4,6))
    ax = fig.add_subplot(1,1,1)

    shift = 0.5
    values = analysis.sitespeptidesproteins(df, site_localization_probability)
    if labels is None:
        labels = ['Sites (Class I)', 'Peptides', 'Proteins']
    if colors is None:
        colors = ['#756bb1', '#bcbddc', '#dadaeb']

    for n, (c, l, v) in enumerate(zip(colors, labels, values)):
        ax.fill_between([0,1,2], np.array([shift,0,shift]) + n, np.array([1+shift,1,1+shift]) + n, color=c, alpha=0.5 )

        ax.text(1, 0.5 + n, "{}\n{:,}".format(l, v), ha='center', color='k', fontsize=16 )
        
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_axis_off()
    
    return ax
    
    
def find_nearest_idx(array,value):
    """

    :param array:
    :param value:
    :return:
    """
    array = array.copy()
    array[np.isnan(array)] = 1
    idx = (np.abs(array-value)).argmin()
    return idx


def rankintensity(df, colors=None, labels_from='Protein names', number_of_annotations=3, show_go_enrichment=False, go_ids_from=None, go_enrichment='function', go_max_labels=8, go_fdr=None):
    """

    :param df:
    :param colors:
    :param labels_from:
    :param number_of_annotations:
    :param show_go_enrichment:
    :param go_ids_from:
    :param go_enrichment:
    :param go_max_labels:
    :param go_fdr:
    :return:
    """

    fig = plt.figure(figsize=(8,8))
    ax = fig.add_subplot(1,1,1)

    labels = df[labels_from].values

    if go_ids_from:
        ids = df[go_ids_from]
    else:
        if 'Proteins' in df.columns.values:
            ids = df['Protein']
        elif 'Protein IDs' in df.columns.values:
            ids = df['Protein IDs']
        else:
            ids = None

    y = np.log10(df['Intensity'].values)

    filt = ~np.array( np.isnan(y) | np.isinf(y) )
    y = y[filt]
    labels = labels[filt]
    if ids is not None:
        ids = ids[filt]

    sort = np.argsort(y)
    y = y[sort]
    labels = labels[sort]
    if ids is not None:
        ids = ids[sort]

    x_max = y.shape[0]
    y_min, y_max = np.min(y), np.max(y)
    yrange = y_max-y_min

    x = np.arange(x_max)

    ax.set_xlim( (-x_max//3,  x_max+x_max//3) )
    ax.set_ylim( (y_min-1,  y_max+1) )

    # Set the dimensions so we can plot the labels correctly.
    ax.scatter(x, y, alpha=0, zorder=-1)

    ax.set_ylabel("Peptide intensity ($log_{10}$)")
    ax.set_xlabel("Peptide rank")

    # Defines ranges over which text can be slotted in (avoid y overlapping)
    slot_size = 0.03 # FIXME: We should calculate this
    text_y_slots = np.arange(0.1, 0.95, slot_size)


    text_y_cross = 0.55
    # Build set of standard x offsets at defined y data points
    # For each y slot, find the (nearest) data y, therefore the x
    text_x_slots = []
    inv =  ax.transLimits.inverted()
    for ys in text_y_slots:
        _, yd = inv.transform( (0, ys) )
        text_x_slots.append( ax.transLimits.transform( (x[find_nearest_idx(y, yd)], 0 ) )[0] )
    text_x_slots = np.array(text_x_slots)

    text_x_slots[text_y_slots < text_y_cross] += 0.15
    text_x_slots[text_y_slots > text_y_cross] -= 0.15

    def annotate_obj(ax, n, labels, xs, ys, idx, yd, ha):
        ni = 1
        previous = {}
        for l, xi, yi in zip(labels, xs, ys):
            if type(l) == str:
                l = get_shortstr(l)

                if l in previous: # Use previous text slot for annotation; skip annotation part
                    axf, ayf = previous[l]

                elif text_y_slots[idx]:
                    axf = text_x_slots[idx]
                    ayf = text_y_slots[idx]
                    text_x_slots[idx] = np.nan
                    text_y_slots[idx] = np.nan

                    ax.text(axf, ayf, l, transform=ax.transAxes,  ha=ha, va='center', color='k')

                    idx += yd
                    ni += 1

                    previous[l] = (axf, ayf)

                ax.annotate("", xy=(xi, yi), xycoords='data',  xytext=(axf, ayf), textcoords='axes fraction',
                        va='center', color='k',
                        arrowprops=dict(arrowstyle='-', connectionstyle="arc3", ec='k', lw=1), zorder=100)

            if ni > n:
                break

    _n = np.min([labels.shape[0], 20])

    annotate_obj(ax, number_of_annotations, labels[-1:-_n:-1], x[-1:-_n:-1], y[-1:-_n:-1], -1, -1, 'right')
    annotate_obj(ax, number_of_annotations, labels[:_n], x[:_n], y[:_n], 0, +1, 'left')

    if go_enrichment and ids is not None:

        # Calculate orders of magnitude (range)
        oomr = int(np.round(np.min(y))), int(np.round(np.max(y)))

        # First -1, last +1
        segments = [[x, x+1] for x in range(*oomr)]
        segments[0][0] -= 3
        segments[-1][1] += 3

        if not isinstance(colors, list):
            if not isinstance(colors, tuple):
                colors = ('#1f77b4', '#d62728')
            # Build a continuous scale from low to high
            cmap = mpl.colors.LinearSegmentedColormap.from_list('custom', list(colors), len(segments))
            colors = [mpl.colors.rgb2hex(cmap(n)) for n in range(len(segments))]

        for n, (s, e) in enumerate(segments):
            mask = (y > s) & (y < e)
            c = x[mask]

            # Comparison relative to background
            gids = list(set(ids[mask]) - set(ids[~mask]))
            go = analysis.go_enrichment(gids, enrichment=go_enrichment, fdr=go_fdr)

            if go is not None:
                labels = [gi[1] for gi in go.index]

                # Filter out less specific GO terms where specific terms exist (simple text matching)
                labels_f = []
                for l in labels:
                    for ll in labels:
                        if l in ll and l != ll:
                            break
                    else:
                        labels_f.append(l)
                labels = labels_f[:go_max_labels]

                yr = ax.transLimits.transform( (0, y[c[0]]) )[1], ax.transLimits.transform( (0, y[c[-1]]) )[1]

                # find axis label point for both start and end
                if yr[0] < text_y_cross:
                    yr = yr[0]-slot_size, yr[1]
                else:
                    yr = yr[0]+slot_size, yr[1]

                yr = find_nearest_idx(text_y_slots, yr[0]), find_nearest_idx(text_y_slots, yr[1])

                yrange = list(range(yr[0], yr[1]))

                # Center ish
                if len(yrange) > len(labels):
                    crop = (len(yrange) - len(labels)) // 2
                    if crop > 1:
                        yrange = yrange[crop:-crop]

                # display ranked top to bottom
                for idx, l in zip(yrange, labels):
                    axf = text_x_slots[idx]
                    ayf = text_y_slots[idx]
                    text_x_slots[idx] = np.nan
                    text_y_slots[idx] = np.nan

                    if ayf > text_y_cross:
                        ha = 'right'
                    else:
                        ha = 'left'
                    ax.text(axf, ayf, l, transform=ax.transAxes, ha=ha, color=colors[n])

            # Calculate GO enrichment terms for each region?
            ax.scatter(x[mask], y[mask], s=15, c=colors[n], lw=0, zorder=100)

    else:
            ax.scatter(x, y, s=15, c='k', lw=0, zorder=100)

    return ax
    
    
def hierarchical(df, cluster_cols=True, cluster_rows=False, n_col_clusters=False, n_row_clusters=False, fcol=None, z_score=0, method='ward', cmap=cm.PuOr_r, return_clusters=False):
    """
    Hierarchical clustering of samples or proteins

    Peform a hiearchical clustering on a pandas DataFrame and display the resulting clustering as a
    heatmap.
    The axis of clustering can be controlled with `cluster_cols` and `cluster_rows`. By default clustering is performed
    along the X-axis, therefore to cluster samples transpose the DataFrame as it is passed, using `df.T`.

    Samples are z-scored along the 0-axis (y) by default. To override this use the `z_score param with the axis to `z_score`
    or alternatively, `None`, to turn it off.

    If a `n_col_clusters` or `n_row_clusters` is specified, this defines the number of clusters to identify and highlight
    in the resulting heatmap. At *least* this number of clusters will be selected, in some instances there will be more
    if 2 clusters rank equally at the determined cutoff.

    If specified `fcol` will be used to colour the axes for matching samples.

    :param df: Pandas `DataFrame to` cluster
    :param cluster_cols: `bool` if `True` cluster along column axis
    :param cluster_rows: `bool` if `True` cluster along row axis
    :param n_col_clusters: `int` the ideal number of highlighted clusters in cols
    :param n_row_clusters: `int` the ideal number of highlighted clusters in rows
    :param fcol: `dict` of label:colors to be applied along the axes
    :param z_score: `int` to specify the axis to Z score or `None` to disable
    :param method: `str` describing cluster method, default ward
    :param cmap: matplotlib colourmap for heatmap
    :param return_clusters: `bool` return clusters in addition to axis
    :return: matplotlib axis, or axis and cluster data
    """


    # helper for cleaning up axes by removing ticks, tick labels, frame, etc.
    def clean_axis(ax):
        """Remove ticks, tick labels, and frame from axis"""
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        ax.set_axis_bgcolor('#ffffff')
        for sp in ax.spines.values():
            sp.set_visible(False)

    def optimize_clusters(clusters, denD, target_n):
        target_n = target_n - 1 # We return edges; not regions
        threshold = np.max(clusters)
        max_iterations = threshold

        i = 0
        while i < max_iterations:
            cc = sch.fcluster(clusters, threshold, 'distance')
            cco = cc[ denD['leaves'] ]
            edges = [n for n in range(cco.shape[0]-1) if cco[n] != cco[n+1]  ]
            n_clusters = len(edges)
            
            if n_clusters == target_n:
                break

            if n_clusters < target_n:
                threshold = threshold // 2

            elif n_clusters > target_n:
                threshold = int( threshold * 1.5 )

            i += 1

        return edges

    dfc = df.copy()

    if z_score is None:
        pass
    elif z_score == 0:
        dfc = (dfc - dfc.median(axis=0)) / dfc.std(axis=0)
    elif z_score == 1:
        dfc = ((dfc.T - dfc.median(axis=1).T) / dfc.std(axis=1).T).T


    # Remove nan/infs
    dfc[np.isinf(dfc)] = 0
    dfc[np.isnan(dfc)] = 0

    #dfc.dropna(axis=0, how='any', inplace=True)

    # make norm
    vmin = dfc.min().min()
    vmax = dfc.max().max()
    vmax = max([vmax, abs(vmin)])  # choose larger of vmin and vmax
    vmin = vmax * -1

    my_norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)

    # dendrogram single color
    sch.set_link_color_palette(['black'])

    # cluster
    if cluster_rows:
        row_pairwise_dists = distance.squareform(distance.pdist(dfc))
        row_clusters = sch.linkage(row_pairwise_dists, method=method)

    if cluster_cols:
        col_pairwise_dists = distance.squareform(distance.pdist(dfc.T))
        col_clusters = sch.linkage(col_pairwise_dists, method=method)

    # heatmap with row names
    fig = plt.figure(figsize=(12, 12))
    heatmapGS = gridspec.GridSpec(2, 2, wspace=0.0, hspace=0.0, width_ratios=[0.25, 1], height_ratios=[0.25, 1])

    if cluster_cols:
        # col dendrogram
        col_denAX = fig.add_subplot(heatmapGS[0, 1])
        col_denD = sch.dendrogram(col_clusters, color_threshold=np.inf)
        clean_axis(col_denAX)

    rowGSSS = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=heatmapGS[1, 0], wspace=0.0, hspace=0.0, width_ratios=[1, 0.05])

    if cluster_rows:
        # row dendrogram
        row_denAX = fig.add_subplot(rowGSSS[0, 0])
        row_denD = sch.dendrogram(row_clusters, color_threshold=np.inf, orientation='right')
        clean_axis(row_denAX)

    row_denD = {
        'leaves':range(0, dfc.shape[0])
    }

    # row colorbar
    if fcol and 'Group' in dfc.index.names:
        class_idx = dfc.index.names.index('Group')

        classcol = [fcol[x] for x in dfc.index.get_level_values(0)[row_denD['leaves']]]
        classrgb = np.array([colorConverter.to_rgb(c) for c in classcol]).reshape(-1, 1, 3)
        row_cbAX = fig.add_subplot(rowGSSS[0, 1])
        row_axi = row_cbAX.imshow(classrgb, interpolation='nearest', aspect='auto', origin='lower')
        clean_axis(row_cbAX)

    # heatmap
    heatmapAX = fig.add_subplot(heatmapGS[1, 1])

    axi = heatmapAX.imshow(dfc.iloc[row_denD['leaves'], col_denD['leaves']], interpolation='nearest', aspect='auto', origin='lower'
                           , norm=my_norm, cmap=cmap)
    clean_axis(heatmapAX)

    # row labels
    if dfc.shape[0] <= 100:
        heatmapAX.set_yticks(range(dfc.shape[0]))
        heatmapAX.yaxis.set_ticks_position('right')
        ylabels = [" ".join([str(t) for t in i]) if type(i) == tuple else str(i) for i in dfc.index[row_denD['leaves']]]
        heatmapAX.set_yticklabels(ylabels)

    # col labels
    if dfc.shape[1] <= 100:
        heatmapAX.set_xticks(range(dfc.shape[1]))
        xlabels = [" ".join([str(t) for t in i]) if type(i) == tuple else str(i) for i in dfc.columns[col_denD['leaves']]]
        xlabelsL = heatmapAX.set_xticklabels(xlabels)
        # rotate labels 90 degrees
        for label in xlabelsL:
            label.set_rotation(90)

    # remove the tick lines
    for l in heatmapAX.get_xticklines() + heatmapAX.get_yticklines():
        l.set_markersize(0)

    heatmapAX.grid('off')

    edges = None

    if cluster_cols and n_col_clusters:
        edges = optimize_clusters(col_clusters, col_denD, n_col_clusters)
        for edge in edges:
            heatmapAX.axvline(edge +0.5, color='k', lw=3)

    if cluster_rows and n_row_clusters:
        edges = optimize_clusters(row_clusters, row_denD, n_row_clusters)
        for edge in edges:
            heatmapAX.axhline(edge +0.5, color='k', lw=3)


    if return_clusters:

        return fig, dfc.iloc[row_denD['leaves'], col_denD['leaves']], edges

    else:
        return fig


def correlation(df, cm=cm.PuOr_r, vmin=None, vmax=None, labels=None, show_scatter=False):
    """

    :param df:
    :param cm:
    :param vmin:
    :param vmax:
    :param labels:
    :param show_scatter:
    :return:
    """
    data = analysis.correlation(df).values

    # Plot the distributions
    fig = plt.figure()
    fig.set_size_inches(10, 10)
    ax = fig.add_subplot(1,1,1)

    if vmin is None:
        vmin = np.nanmin(data)

    if vmax is None:
        vmax = np.nanmax(data)

    n_dims = data.shape[0]

    # If showing scatter plots, set the inlay portion to np.nan
    if show_scatter:

        # Get the triangle, other values will be zeroed
        idx = np.tril_indices(n_dims)
        data[idx] = np.nan

    cm.set_bad('w', 1.)
    i = ax.imshow(data, cmap=cm, vmin=vmin, vmax=vmax, interpolation='none')
    fig.colorbar(i)
    fig.axes[0].grid('off')

    if show_scatter:
        figo = mpl.figure.Figure(figsize=(n_dims, n_dims))
        # Create a dummy Agg canvas so we don't have to display/output this intermediate
        canvas = FigureCanvasAgg(figo)

        for x in range(n_dims):
            for y in range(x, n_dims):

                ax = figo.add_subplot(n_dims, n_dims, y*n_dims+x+1)

                xd = df.values[:, x]
                yd = df.values[:, y]

                ax.scatter(xd, yd, lw=0, s=5, c='k', alpha=0.2)
                ax.grid('off')
                ax.axis('off')

        figo.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        raw = BytesIO()
        figo.savefig(raw, format='png', bbox_inches=0, transparent=True)
        del figo

        raw.seek(0)
        img = mplimg.imread(raw)
        ax2 = fig.add_axes(fig.axes[0].get_position(), label='image', zorder=1)
        ax2.axis('off')
        ax2.imshow(img)

    if labels:
        # Build labels from the supplied axis
        labels = df.columns.get_level_values(labels)

        fig.axes[0].set_xticks(range(n_dims))
        fig.axes[0].set_xticklabels(labels, rotation=90)

        fig.axes[0].set_yticks(range(n_dims))
        fig.axes[0].set_yticklabels(labels)

    return fig


def comparedist(df1, df2, bins=50):
    """
    Compare two distributions with visualisations of:
     - individual and combined distributions
     - distribution of non-common values
     - distribution of non-common values vs. each side

    Plot distribution as area (fill_between) + mean, median vertical bars
    """

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(30, 10))

    xr = np.nanmin( [np.nanmin(df1), np.nanmin(df2)] ), np.nanmax( [np.nanmax(df1), np.nanmax(df2)] )

    def areadist(ax, v, xr, c, bins=100, by=None, alpha=1):
        """
        Plot the histogram distribution but as an area plot
        """
        y, x = np.histogram(v[~np.isnan(v)], bins)
        x = x[:-1]

        if by is None:
            by = np.zeros( (bins, ) )

        ax.fill_between(x, y, by, facecolor=c, alpha=alpha)
        return y

    ax1.set_title('Distributions of A and B')
    areadist(ax1, df2.values, xr, c='r', bins=bins)
    areadist(ax1, df1.values, xr, c='k', bins=bins, alpha=0.3)
    ax1.set_xlabel('Value')
    ax1.set_ylabel('Count')

    ax2.set_title('Distributions of A and values unique to B')
    # Calculate what is different isolate those values
    areadist(ax2, df2.values[ df2.values != df1.values ], xr, c='r', bins=bins)
    areadist(ax2, df1.values, xr, c='k', bins=bins, alpha=0.3)
    ax2.set_xlabel('Value')
    ax2.set_ylabel('Count')

    # Calculate (at the lowest column index level) the difference between
    # distribution of unique values, vs those in common
    # Get indices of difference
    dfc= df1.copy()
    dfc[:] = (df2.values != df1.values).astype(int)
    for i in dfc.columns.values:
        dfc[i[:-1]] = np.max(dfc[i[:-1]].values, axis=1)

    ax3.set_title('Distributions of associated values of A and substituted values in B')
    areadist(ax3, df2.values[ df2.values != df1.values ], xr, c='r')
    areadist(ax3, df1.values[ dfc.values == 1 ], xr, c='k', alpha=0.3)
    ax3.set_xlabel('Value')
    ax3.set_ylabel('Count')

    return fig

