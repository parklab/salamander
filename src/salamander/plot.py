import warnings
from functools import wraps

import fastcluster
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import umap
from scipy.cluster import hierarchy
from scipy.spatial.distance import pdist
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

from .consts import COLORS_INDEL83, COLORS_SBS96, INDEL_TYPES_83, SBS_TYPES_96
from .utils import match_to_catalog


def paper_style(func):
    @wraps(func)
    def rc_wrapper(*args, **kwargs):
        sns.set_context("notebook")
        sns.set_style("ticks")

        params = {
            "axes.edgecolor": "black",
            "axes.labelsize": 14,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titlesize": 16,
            "errorbar.capsize": 3,
            "font.family": "DejaVu Sans",
            "legend.fontsize": 12,
            "lines.markersize": 8,
            "pdf.fonttype": 42,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
        }

        mpl.rcParams.update(params)

        return func(*args, **kwargs)

    return rc_wrapper


def _annotate_plot(
    ax, data, annotations, ha="left", fontsize="medium", color="black", **kwargs
):
    for data_point, annotation in zip(data, annotations):
        ax.text(
            data_point[0] + 0.01,
            data_point[1] + 0.01,
            annotation,
            ha=ha,
            fontsize=fontsize,
            color=color,
            **kwargs,
        )


@paper_style
def scatter_1d(
    data: np.ndarray, annotations=None, annotation_kwargs=None, ax=None, **kwargs
):
    if data.ndim != 1:
        raise ValueError(f"The datapoints of {data} (rows) have to be one-dimensional.")

    annotation_kwargs = {} if annotation_kwargs is None else annotation_kwargs.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 1))

    y_coordinates = np.zeros_like(data)

    ax.spines[["left", "bottom"]].set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.axhline(y=0, color="black", zorder=1)
    sns.scatterplot(x=data, y=y_coordinates, ax=ax, zorder=2, **kwargs)

    if annotations is not None:
        annotation_data = np.vstack([data, y_coordinates]).T
        _annotate_plot(ax, annotation_data, annotations, **annotation_kwargs)

    return ax


@paper_style
def scatter_2d(data, annotations=None, annotation_kwargs=None, ax=None, **kwargs):
    """
    The rows (!) of 'data' are assumed to be the data points.
    """
    if data.shape[1] != 2:
        raise ValueError(f"The datapoints of {data} (rows) have to be two-dimensional.")

    annotation_kwargs = {} if annotation_kwargs is None else annotation_kwargs.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))

    ax.set(xlabel="x", ylabel="y")
    sns.scatterplot(x=data[:, 0], y=data[:, 1], ax=ax, **kwargs)

    if annotations is not None:
        _annotate_plot(ax, data, annotations, **annotation_kwargs)

    return ax


@paper_style
def pca_2d(data, annotations=None, annotation_kwargs=None, ax=None, **kwargs):
    """
    The rows (!) of 'data' are assumed to be the data points.
    """
    data_projected = PCA(n_components=2).fit_transform(data)
    annotation_kwargs = {} if annotation_kwargs is None else annotation_kwargs.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))

    ax.set(xlabel="PC1", ylabel="PC2")
    sns.scatterplot(x=data_projected[:, 0], y=data_projected[:, 1], ax=ax, **kwargs)

    if annotations is not None:
        _annotate_plot(ax, data_projected, annotations, **annotation_kwargs)

    return ax


@paper_style
def tsne_2d(
    data, perplexity=30, annotations=None, annotation_kwargs=None, ax=None, **kwargs
):
    """
    The rows (!) of 'data' are assumed to be the single data points.
    """
    annotation_kwargs = {} if annotation_kwargs is None else annotation_kwargs.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data_projected = TSNE(perplexity=perplexity).fit_transform(data)

    ax.set(xlabel="t-SNE1", xticks=[], ylabel="t-SNE2", yticks=[])
    sns.scatterplot(x=data_projected[:, 0], y=data_projected[:, 1], ax=ax, **kwargs)

    if annotations is not None:
        _annotate_plot(ax, data_projected, annotations, **annotation_kwargs)

    return ax


@paper_style
def umap_2d(
    data,
    n_neighbors=15,
    min_dist=0.1,
    annotations=None,
    annotation_kwargs=None,
    ax=None,
    **kwargs,
):
    """
    The rows (!) of 'data' are assumed to be the single data points.
    """
    annotation_kwargs = {} if annotation_kwargs is None else annotation_kwargs.copy()

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))

    n_neighbors = min(n_neighbors, len(data) - 1)
    data_projected = umap.UMAP(
        n_neighbors=n_neighbors, min_dist=min_dist
    ).fit_transform(data)

    ax.set(xlabel="UMAP1", xticks=[], ylabel="UMAP2", yticks=[])
    sns.scatterplot(x=data_projected[:, 0], y=data_projected[:, 1], ax=ax, **kwargs)

    if annotations is not None:
        _annotate_plot(ax, data_projected, annotations, **annotation_kwargs)

    return ax


@paper_style
def plot_history(function_values, figtitle="", ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()

    ax.set(title=figtitle, xlabel="training step", ylabel="objective function")
    ax.plot(range(len(function_values)), function_values, **kwargs)

    return ax


@paper_style
def corr_plot(
    corr: pd.DataFrame, figsize=(6, 6), cmap="vlag", annot=True, fmt=".2f", **kwargs
):
    linkage = hierarchy.linkage(corr)
    clustergrid = sns.clustermap(
        corr,
        row_linkage=linkage,
        figsize=figsize,
        vmin=-1,
        vmax=1,
        cmap=cmap,
        annot=annot,
        fmt=fmt,
        **kwargs,
    )

    return clustergrid


def _get_colors_signature_plot(colors, mutation_types):
    """
    Given the colors argument of sigplot_bar and the mutation types, return the
    colors used in the signature bar chart.
    """
    n_features = len(mutation_types)

    if colors == "SBS96" or (n_features == 96 and all(mutation_types == SBS_TYPES_96)):
        if n_features != 96:
            raise ValueError(
                "The standard SBS colors can only be used "
                "when the signatures have 96 features."
            )

        colors = COLORS_SBS96

    elif colors == "Indel83" or (
        n_features == 83 and all(mutation_types == INDEL_TYPES_83)
    ):
        if n_features != 83:
            raise ValueError(
                "The standard Indel colors can only be used "
                "when the signatures have 83 features."
            )

        colors = COLORS_INDEL83

    elif type(colors) in [str, tuple]:
        colors = n_features * [colors]

    elif type(colors) is list:
        if len(colors) != n_features:
            raise ValueError(
                f"The list of colors must be of length n_features={n_features}."
            )

    else:
        colors = n_features * ["gray"]

    return colors


@paper_style
def _signature_plot(
    signature, colors=None, annotate_mutation_types=False, ax=None, **kwargs
):
    """
    Inputs:
    -------
    signature: pd.Signature
        Signature with mutation types and name.

    colors: str, tuple or list
        Can be set to 'SBS96' or 'Indel83' to use the standard bar colors
        for these mutation types.
        Otherwise, when a single string or tuple is provided,
        all bars will have the same color. Alternatively,
        a list can be used to specifiy the color of each bar individually.

    ax:
        A single matplotlib Axes in which to draw the plot.

    kwargs: dict
        Any keyword arguments to be passed to matplotlibs ax.bar
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(4, 1))

    signature_normalized = signature / signature.sum(axis=0)
    mutation_types = signature.index
    colors = _get_colors_signature_plot(colors, mutation_types)

    ax.set_title(signature_normalized.columns[0])
    ax.spines["left"].set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_xlim((-1, len(mutation_types)))

    ax.bar(
        mutation_types,
        signature_normalized.iloc[:, 0],
        linewidth=0,
        color=colors,
        **kwargs,
    )

    if annotate_mutation_types:
        ax.set_xticks(mutation_types)
        ax.set_xticklabels(
            mutation_types, family="monospace", fontsize=4, ha="center", rotation=90
        )

    else:
        ax.set_xticks([])

    return ax


@paper_style
def signature_plot(
    signature,
    catalog=None,
    colors=None,
    annotate_mutation_types=False,
    ax=None,
    **kwargs,
):
    """
    Inputs:
    -------
    signature: pd.Signature
        Signature with mutation types and name.

    catalog: pd.DataFrame
        If a catalog is provided, the single best matching catalog signature
        will also be plotted.

    colors: str, tuple or list
        Can be set to 'SBS96' or 'Indel83' to use the standard bar colors
        for these mutation types.
        Otherwise, when a single string or tuple is provided,
        all bars will have the same color. Alternatively,
        a list can be used to specifiy the color of each bar individually.

    ax:
        Axes in which to draw the plot. A single Axes if catalog is None;
        two Axes if a catalog is given.

    kwargs: dict
        Any keyword arguments to be passed to matplotlibs ax.bar
    """
    if catalog is None:
        if ax is None:
            _, ax = plt.subplots(figsize=(4, 1))

        signatures = [signature]
        axes = [ax]

    else:
        if ax is None:
            _, ax = plt.subplots(1, 2, figsize=(8, 1))

        matched_signature = match_to_catalog(signature, catalog, metric="cosine")
        signatures = [signature, matched_signature]
        axes = ax

    for sig, axis in zip(signatures, axes):
        _signature_plot(
            sig,
            colors=colors,
            annotate_mutation_types=annotate_mutation_types,
            ax=axis,
            **kwargs,
        )

    if catalog is None:
        return axes[0]

    return axes


@paper_style
def signatures_plot(
    signatures,
    catalog=None,
    colors=None,
    annotate_mutation_types=False,
    axes=None,
    **kwargs,
):
    """
    Inputs:
    -------
    signatures : pd.DataFrame
        Named signatures of shape (n_features, n_signatures)

    catalog: pd.DataFrame
        If a catalog is provided, the best matching catalog signatures
        will also be plotted.

    axes : list
        Axes in which to draw the plot. Multiple Axes if more than one signature
        is provided or a catalog is given. Otherwise a single axis.
        When a catalog is provided, axes is expected to be of shape (n_signatures, 2).
    """
    n_signatures = signatures.shape[1]

    if n_signatures == 1:
        ax = signature_plot(
            signatures,
            catalog=catalog,
            colors=colors,
            annotate_mutation_types=annotate_mutation_types,
            ax=axes,
            **kwargs,
        )
        return ax

    if axes is None:
        if catalog is None:
            _, axes = plt.subplots(n_signatures, 1, figsize=(4, n_signatures))

        else:
            _, axes = plt.subplots(n_signatures, 2, figsize=(8, n_signatures))

    for ax, signature in zip(axes.flatten(), signatures):
        signature_plot(
            signatures[[signature]],
            catalog=catalog,
            colors=colors,
            annotate_mutation_types=annotate_mutation_types,
            ax=ax,
            **kwargs,
        )
    plt.tight_layout()

    return axes


def _reorder_exposures(exposures: pd.DataFrame, reorder_signatures=True):
    """
    Reorder the samples using hierarchical clustering and
    reorder the signatures by their total relative exposure.
    """
    exposures_normalized = exposures / exposures.sum(axis=0)

    d = pdist(exposures_normalized.T)
    linkage = fastcluster.linkage(d)
    # get the optimal sample order that is consistent
    # with the hierarchical clustering linkage
    sample_order = hierarchy.leaves_list(hierarchy.optimal_leaf_ordering(linkage, d))
    samples_reordered = exposures_normalized.columns[sample_order]
    exposures_reordered = exposures_normalized[samples_reordered]

    # order the signatures by their total exposure
    if reorder_signatures:
        signatures_reordered = (
            exposures_reordered.sum(axis=1).sort_values(ascending=False).index
        )
        exposures_reordered = exposures_reordered.reindex(signatures_reordered)

    return exposures_reordered


@paper_style
def exposures_plot(
    exposures: pd.DataFrame,
    reorder_signatures=True,
    annotate_samples=True,
    colors=None,
    ncol_legend=1,
    ax=None,
    **kwargs,
):
    """
    Visualize the exposures using a stacked bar chart.
    """
    n_signatures, n_samples = exposures.shape
    exposures_reordered = _reorder_exposures(
        exposures, reorder_signatures=reorder_signatures
    )
    samples = exposures_reordered.columns

    if ax is None:
        _, ax = plt.subplots(figsize=(0.3 * n_samples, 4))

    if colors is None:
        colors = list(sns.color_palette("deep")) * (1 + n_signatures // 10)

    bottom = np.zeros(n_samples)

    for signature, color in zip(exposures_reordered.T, colors):
        signature_exposures = exposures_reordered.T[signature].to_numpy()
        ax.bar(
            np.arange(n_samples),
            signature_exposures,
            color=color,
            width=1,
            label=signature,
            linewidth=0,
            bottom=bottom,
            **kwargs,
        )
        bottom += signature_exposures

    if annotate_samples:
        ax.set_xticks(np.arange(n_samples))
        ax.set_xticklabels(samples, rotation=90, ha="center", fontsize=10)

    else:
        ax.get_xaxis().set_visible(False)

    ax.set_title("Sample exposures")
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.legend(loc="center left", bbox_to_anchor=(0.975, 0.5), ncol=ncol_legend)

    return ax
