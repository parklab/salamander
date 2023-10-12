from abc import ABC, abstractmethod

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..plot import corr_plot, exposures_plot, paper_style, signatures_plot
from ..utils import type_checker, value_checker


class SignatureNMF(ABC):
    """
    The abstract class SignatureNMF unifies the structure of
    multiple NMF algorithms used for signature analysis.

    Common properties and methods of all algorithms are indicated,
    i.e. have to be implemented by child classes, or implemented. Overview:

    Every child class has to implement the following attributes:

        - signatures: pd.DataFrame
            The signature matrix including mutation type names and signature names

        - exposures: pd.DataFrames
            The exposure matrix including the signature names and sample names

        - _n_parameters: int
            The number of parameters fitted by the NMF algorithm.
            This is needed to compute the Bayesian Information Criterion (BIC)

        - reconstruction_error: float
            The reconstruction error between the count matrix and
            the reconstructed count matrix.

        - samplewise_reconstruction_error: np.ndarray
            The samplewise reconstruction error between the sample counts and
            the reconstructed sample counts.

        - objective: str
            "minimize" or "maximize". Whether the NMF algorithm maximizes or
            minimizes the objective function. Some algorithms maximize a likelihood,
            others minimize a distance. The distinction is useful for filtering NMF runs
            based on the fitted objective function value downstream.

        - corr_signatures: pd.DataFrame
            The signature correlation matrix

        - corr_samples: pd.DataFrame
            The sample correlation matrix


    Every child class has to implement the following methods:

        - objective_fuction:
            The objective function to optimize when running the algorithm

        - loglikelihood:
            The loglikelihood of the underyling generative model

        - _initialize:
            A method to initialize all model parameters before fitting

        - fit:
            Run the NMF algorithm for a given mutation count data. Every
            fit method should also implement a "refitting version", where the signatures
            W are known in advance and fixed.

        - plot_embeddings:
            Plot the sample (and potentially the signature) embeddings in 2D.


    The following attributes and methods are implemented in SignatureNMF:

        - data_reconstructed: pd.DataFrame
            The recovered mutation count data given
            the current signatures and exposures.

        - X_reconstructed: np.ndarray
            The recovered mutation count matrix given
            the current signatures and exposures

        - bic: float
            The value of the Bayesian Information Criterion (BIC)

        - _setup_parameters_fitting:
            Perform parameter checks and add the input mutation counts matrix
            as an attributes

        - plot_signatures:
            Plot the signatures using the signatures_plot function implemented in
            the plot module

        - plot_correlation:
            Plot the correlation of either the signatures or exposures
            using the corr_plot function implemented in the plot module

    More specific docstrings are written for the respective attributes and methods.
    """

    def __init__(
        self,
        n_signatures=1,
        init_method="nndsvd",
        min_iterations=500,
        max_iterations=10000,
        tol=1e-7,
    ):
        """
        Input:
        ------
        n_signatures: int
            The number of underlying signatures that are assumed to
            have generated the mutation count data

        init_method: str
            The initialization method for the NMF algorithm

        min_iterations: int
            The minimum number of iterations to perform by the NMF algorithm

        max_iterations: int
            The maximum number of iterations to perform by the NMF algorithm

        tol: float
            The NMF algorithm is converged when the relative change of
            the objective function of one iteration is smaller
            than the tolerance 'tol'.
        """
        init_methods = [
            "custom",
            "flat",
            "hierarchical_cluster",
            "nndsvd",
            "nndsvda",
            "nndsvdar",
            "random",
            "separableNMF",
        ]
        value_checker("init_method", init_method, init_methods)

        self.n_signatures = n_signatures
        self.signature_names = np.array([f"Sig{k+1}" for k in range(n_signatures)])
        self.init_method = init_method
        self.min_iterations = min_iterations
        self.max_iterations = max_iterations
        self.tol = tol

        # initialize data/fitting dependent attributes
        self.X = None
        self.n_features = 0
        self.n_samples = 0
        self.mutation_types = np.empty(0, dtype=str)
        self.sample_names = np.empty(0, dtype=str)
        self.history = {}

    @property
    @abstractmethod
    def signatures(self) -> pd.DataFrame:
        """
        Extract the mutational signatures as a pandas dataframe.
        """
        pass

    @property
    @abstractmethod
    def exposures(self) -> pd.DataFrame:
        """
        Extract the signature exposures of samples as a pandas dataframe.
        """
        pass

    @property
    def data_reconstructed(self) -> pd.DataFrame:
        return (self.signatures @ self.exposures).astype(int)

    @property
    def X_reconstructed(self) -> np.ndarray:
        return self.data_reconstructed.values

    @property
    @abstractmethod
    def reconstruction_error(self) -> float:
        """
        The reconstruction error between the count matrix and
        the reconstructed count matrix.
        """
        pass

    @property
    @abstractmethod
    def samplewise_reconstruction_error(self) -> np.ndarray:
        """
        The samplewise reconstruction error between the sample counts and
        the reconstructed sample counts.
        """
        pass

    @abstractmethod
    def objective_function(self) -> float:
        """
        The objective function to be optimized during fitting.
        """
        pass

    @abstractmethod
    def loglikelihood(self) -> float:
        """
        The log-likelihood of the underlying generative model.
        """
        pass

    @property
    @abstractmethod
    def _n_parameters(self) -> int:
        """
        Every child class has to implement a function returning
        the number of parameters estimated by the respective model.
        This is allows to, for example, implement the BIC
        (Bayesian information criterion). The BIC can be used to
        estimate the optimal number of signatures.
        """
        pass

    @property
    def bic(self) -> float:
        """
        Bayesian information criterion (BIC).
        Can only be called after the _setup_parameters_fitting function as it
        requires the number of samples be an attribute.
        """
        return self._n_parameters * np.log(self.n_samples) - 2 * self.loglikelihood()

    def _check_given_signatures(self, given_signatures: pd.DataFrame):
        """
        Check if the given signatures are compatible with the
        number of signatures of the algorithm and the
        mutation types of the input data and.

        given_signatures: pd.DataFrame
            Known signatures that should be fixed by the algorithm.
        """
        type_checker("given_signatures", given_signatures, pd.DataFrame)
        given_mutation_types = given_signatures.index.to_numpy(dtype=str)
        compatible = (
            np.array_equal(given_mutation_types, self.mutation_types)
            and given_signatures.shape[1] == self.n_signatures
        )

        if not compatible:
            raise ValueError(
                f"You have to provide {self.n_signatures} signatures with "
                f"mutation types matching to your data."
            )

    @abstractmethod
    def _initialize(self):
        """
        Initialize model parameters and attributes before fitting.
        Enforcing the existence of _initialize unifies the implementation of
        the NMF algorithms.

        Example:

            Before running the Lee & Seung NMF multiplicative update rules to
            decompose the mutation count matrix X into a signature matrix W and
            an exposure matrix H, both W and H have to be initialized.
        """
        pass

    def _setup_data_parameters(self, data: pd.DataFrame):
        """
        Perform parameter checks before running the fit method.

        Input:
        ------
        data: pd.DataFrame
            The mutation count pandas dataframe with indices and column names.
            Samples are expected to corresponding to columns.
        """
        type_checker("data", data, pd.DataFrame)
        self.X = data.values
        self.n_features, self.n_samples = data.shape
        self.mutation_types = data.index.values.astype(str)
        self.sample_names = data.columns.values.astype(str)

    @abstractmethod
    def fit(self, data: pd.DataFrame, given_signatures=None):
        """
        Fit the model parameters. Child classes are expected to handle
        'given_signatures' appropriately.

        Input:
        ------
        data: pd.DataFrame
            The named mutation count data of shape (n_features, n_samples).

        given_signatures: pd.DataFrame, by default None
            In the case of refitting, 'given_signatures'
            are the a priori known signatures.
            The number of signatures has to match to the NMF algorithm
            instance and the mutation type names have to match to the names
            of the mutation count data.
        """
        pass

    @paper_style
    def plot_signatures(
        self,
        catalog=None,
        colors=None,
        annotate_mutation_types=False,
        axes=None,
        outfile=None,
        **kwargs,
    ):
        """
        Plot the signatures, see plot.py for the implementation of signatures_plot.

        Input:
        ------
        **kwargs:
            arguments to be passed to signatures_plot
        """
        axes = signatures_plot(
            self.signatures,
            catalog=catalog,
            colors=colors,
            annotate_mutation_types=annotate_mutation_types,
            axes=axes,
            **kwargs,
        )

        if outfile is not None:
            plt.savefig(outfile, bbox_inches="tight")

        return axes

    @paper_style
    def plot_exposures(
        self,
        reorder_signatures=True,
        annotate_samples=True,
        colors=None,
        ncol_legend=1,
        ax=None,
        outfile=None,
        **kwargs,
    ):
        """
        Visualize the exposures as a stacked bar chart,
        see plot.py for the implementation.

        Input:
        ------
        **kwargs:
            arguments to be passed to exposure_plot
        """
        ax = exposures_plot(
            exposures=self.exposures,
            reorder_signatures=reorder_signatures,
            annotate_samples=annotate_samples,
            colors=colors,
            ncol_legend=ncol_legend,
            ax=ax,
            **kwargs,
        )

        if outfile is not None:
            plt.savefig(outfile, bbox_inches="tight")

        return ax

    @property
    @abstractmethod
    def corr_signatures(self) -> pd.DataFrame:
        """
        Every child class of SignatureNMF has to implement a function that
        returns the signature correlation matrix as a pandas dataframe.
        """
        pass

    @property
    @abstractmethod
    def corr_samples(self) -> pd.DataFrame:
        """
        Every child class of SignatureNMF has to implement a function that
        returns the sample correlation matrix as a pandas dataframe.
        """
        pass

    def plot_correlation(self, data="signatures", annot=False, outfile=None, **kwargs):
        """
        Plot the correlation matrix of the signatures or samples.
        See plot.py for the implementation of corr_plot.

        Input:
        ------
        *args, **kwargs:
            arguments to be passed to corr_plot
        """
        value_checker("data", data, ["signatures", "samples"])

        if data == "signatures":
            corr = self.corr_signatures

        else:
            corr = self.corr_samples

        clustergrid = corr_plot(corr, annot=annot, **kwargs)

        if outfile is not None:
            plt.savefig(outfile, bbox_inches="tight")

        return clustergrid

    @abstractmethod
    def plot_embeddings(self):
        """
        Plot the sample (and potentially the signature) embeddings in 2D.
        """
        pass