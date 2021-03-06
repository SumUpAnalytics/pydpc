# This file is part of pydpc.
#
# Copyright 2016 Christoph Wehmeyer
#
# pydpc is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sklearn.metrics.pairwise import cosine_distances as skcosine_distances
from sklearn.metrics.pairwise import euclidean_distances as skeuclidean_distances
from scipy.sparse import issparse
import numpy as _np
import matplotlib.pyplot as _plt
from . import core as _core

__all__ = ['Cluster']

class Distances(object):
    def __init__(self, points, metric):
        
        # ADDED: we add the possibility for the user to chose the euclidean or
        # the cosine distance, with 0 -> euclidean, 1 -> cosine
        if metric == 'euclidean':
            self.metric = 0
        elif metric == 'cosine':
            self.metric = 1
        else:
            raise ValueError("Metric must be 'euclidean' or 'cosine'")
                             
        self.points = points
        self.npoints = self.points.shape[0]
        
        # If the matrix is not sparse, we use the c++ core to compute the pairwise distances
        if not issparse(self.points):
            self.distances = _core.get_distances(self.points, self.metric)
        # Else we use sklearn pairwise distances for sparse matrices. 
        else: 
            if self.metric: # Cosine distance:
                self.distances = skcosine_distances(self.points)
            else: # Euclidean distance
                self.distances = skeuclidean_distances(self.points)
                
        self.max_distance = self.distances.max()

class Density(Distances):
    def __init__(self, points, fraction, metric):
        super(Density, self).__init__(points, metric)
        self.fraction = fraction
        self.kernel_size = _core.get_kernel_size(self.distances, self.fraction)
        self.density = _core.get_density(self.distances, self.kernel_size)

class Graph(Density):
    def __init__(self, points, fraction, metric):
        super(Graph, self).__init__(points, fraction, metric)
        self.order = _np.ascontiguousarray(_np.argsort(self.density).astype(_np.intc)[::-1])
        self.delta, self.neighbour = _core.get_delta_and_neighbour(
            self.order, self.distances, self.max_distance)

class Cluster(Graph):
    def __init__(self, points, fraction=0.02, metric = 'euclidean', autoplot=True):
        super(Cluster, self).__init__(points, fraction, metric)
        self.autoplot = autoplot
        if self.autoplot:
            self.draw_decision_graph()
    def draw_decision_graph(self, min_density=None, min_delta=None):
        fig, ax = _plt.subplots(figsize=(5, 5))
        ax.scatter(self.density, self.delta, s=40)
        if min_density is not None and min_delta is not None:
            ax.plot(
                [min_density, self.density.max()], [min_delta, min_delta], linewidth=2, color="red")
            ax.plot(
                [min_density, min_density], [min_delta, self.delta.max()], linewidth=2, color="red")
        ax.set_xlabel(r"density", fontsize=20)
        ax.set_ylabel(r"delta / a.u.", fontsize=20)
        ax.tick_params(labelsize=15)
        return fig, ax
    def assign(self, min_density, min_delta, border_only=False):
        self.min_density = min_density
        self.min_delta = min_delta
        self.border_only = border_only
        if self.autoplot:
            self.draw_decision_graph(self.min_density, self.min_delta)
        self._get_cluster_indices()
        self.membership = _core.get_membership(self.clusters, self.order, self.neighbour)
        self.border_density, self.border_member = _core.get_border(
            self.kernel_size, self.distances, self.density, self.membership, self.nclusters)
        self.halo_idx, self.core_idx = _core.get_halo(
            self.density, self.membership,
            self.border_density, self.border_member.astype(_np.intc), border_only=border_only)
    def _get_cluster_indices(self):
        self.clusters = _np.intersect1d(
            _np.where(self.density > self.min_density)[0],
            _np.where(self.delta > self.min_delta)[0], assume_unique=True).astype(_np.intc)
        self.nclusters = self.clusters.shape[0]
