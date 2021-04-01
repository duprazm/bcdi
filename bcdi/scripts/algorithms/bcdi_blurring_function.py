#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-present : DESY PHOTON SCIENCE
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

import matplotlib as mpl
from matplotlib import pyplot as plt
from numbers import Real
import numpy as np
import pathlib
import tkinter as tk
from tkinter import filedialog
import sys
sys.path.append('D:/myscripts/bcdi/')
import bcdi.algorithms.algorithms_utils as algo
import bcdi.facet_recognition.facet_utils as fu
import bcdi.graph.graph_utils as gu
import bcdi.postprocessing.postprocessing_utils as pu
import bcdi.utils.utilities as util
import bcdi.utils.validation as valid

helptext = """
Load a 3D BCDI reconstruction (.npz file) containing the field 'amp'. After defining a support using a threshold on the 
normalized amplitude, calculate the blurring function by Richardson-Lucy deconvolution. Extract the resolution from 
this blurring function in arbitrary direction. See M. Cherukara et al. Anisotropic nano-scale resolution in 3D 
Bragg coherent diffraction imaging. Appl. Phys. Lett. 113, 203101 (2018); https://doi.org/10.1063/1.5055235
"""

datadir = "D:/data/P10_2nd_test_isosurface_Dec2020/data_nanolab/dataset_2_pearson97.5_newpsf/result/"
savedir = datadir + 'test/'
isosurface_threshold = 0.2
phasing_shape = None  # shape of the dataset used during phase retrieval (after an eventual binning in PyNX).
# tuple of 3 positive integers or None, if None the actual shape will be considered.
upsampling_factor = 2  # integer, 1=no upsampling_factor, 2=voxel size divided by 2 etc...
rl_iterations = 50   # number of iterations for the Richardson-Lucy algorithm
comment = ''  # string to add to the filename when saving, should start with "_"
tick_length = 10  # in plots
tick_width = 2  # in plots
debug = True  # True to see more plots
min_offset = 1e-6  # object and support voxels with null value will be set to this number, in order to avoid
# divisions by zero
##########################
# end of user parameters #
##########################

#############################
# define default parameters #
#############################
colors = ('b', 'g', 'r', 'c', 'm', 'y', 'k')  # for plots
markers = ('.', 'v', '^', '<', '>', 'x', '+', 'o')  # for plots
mpl.rcParams['axes.linewidth'] = tick_width  # set the linewidth globally
validation_name = 'bcdi_blurring_function'

#########################
# check some parameters #
#########################
if not datadir.endswith('/'):
    datadir += '/'
savedir = savedir or datadir
if not savedir.endswith('/'):
    savedir += '/'
pathlib.Path(savedir).mkdir(parents=True, exist_ok=True)
valid.valid_item(isosurface_threshold, allowed_types=Real, min_included=0, max_excluded=1, name=validation_name)
valid.valid_container(phasing_shape, container_types=(tuple, list, np.ndarray), allow_none=True, item_types=int,
                      min_excluded=0, name=validation_name)
valid.valid_item(value=upsampling_factor, allowed_types=int, min_included=1, name=validation_name)
valid.valid_container(comment, container_types=str, name=validation_name)
if len(comment) != 0 and not comment.startswith('_'):
    comment = '_' + comment
valid.valid_item(tick_length, allowed_types=int, min_excluded=0, name=validation_name)
valid.valid_item(tick_width, allowed_types=int, min_excluded=0, name=validation_name)
valid.valid_item(debug, allowed_types=bool, name=validation_name)
valid.valid_item(min_offset, allowed_types=Real, min_included=0, name=validation_name)
valid.valid_item(rl_iterations, allowed_types=int, min_excluded=0, name=validation_name)

#########################################################
# load the 3D recontruction , output of phase retrieval #
#########################################################
plt.ion()
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(initialdir=datadir, title="Select the reconstructed object",
                                       filetypes=[("NPZ", "*.npz"), ("NPY", "*.npy"),
                                                  ("CXI", "*.cxi"), ("HDF5", "*.h5")])
if file_path.endswith('npz'):
    kwarg = {'fieldname': 'amp'}
else:
    kwarg = {}

obj, extension = util.load_file(file_path, **kwarg)
if extension == '.h5':
    comment = comment + '_mode'

if phasing_shape is None:
    phasing_shape = obj.shape

if upsampling_factor > 1:
    obj, _ = fu.upsample(array=obj, upsampling_factor=upsampling_factor, debugging=debug)
    print(f'Upsampled object shape = {obj.shape}')

######################
# define the support #
######################
obj = abs(obj)
min_obj = obj[np.nonzero(obj)].min()
obj = obj / min_obj  # normalize to the non-zero min to avoid dividing by small numbers
obj[obj == 0] = min_offset  # avoid dividing by 0
support = np.zeros(obj.shape)
support[obj >= isosurface_threshold * obj.max()] = 1
support[support == 0] = min_offset

if debug:
    gu.multislices_plot(obj, sum_frames=False, reciprocal_space=False, is_orthogonal=True,
                        plot_colorbar=True, title='normalized modulus')
    gu.multislices_plot(support, sum_frames=False, reciprocal_space=False, is_orthogonal=True, vmin=0, vmax=1, 
                        plot_colorbar=True, title=f'support at threshold {isosurface_threshold}')
    
###################################
# calculate the blurring function #
###################################
psf_guess = pu.gaussian_window(window_shape=obj.shape, sigma=0.1, mu=0.0, debugging=debug)
psf_guess = psf_guess / min_obj
psf_partial_coh, error = algo.partial_coherence_rl(measured_intensity=obj, coherent_intensity=support,
                                                   iterations=rl_iterations, debugging=False, scale='linear',
                                                   is_orthogonal=True, reciprocal_space=False, guess=psf_guess)

psf_partial_coh = abs(psf_partial_coh) / abs(psf_partial_coh).max()
print(f"error minimum at iteration {np.unravel_index(error.argmin(), shape=(rl_iterations,))}")

###############################################
# plot the retrieved psf and the error metric #
###############################################
gu.multislices_plot(psf_partial_coh, scale='linear', sum_frames=False, title='psf', reciprocal_space=False,
                    is_orthogonal=True, plot_colorbar=True)
_, ax = plt.subplots(figsize=(12, 9))
ax.plot(error, 'r.')
ax.set_yscale('log')
ax.set_xlabel('iteration number')
ax.set_ylabel('difference between consecutive iterates')

################
# save the psf #
################
np.savez_compressed(savedir + 'psf.npz', nb_iter=rl_iterations, isosurface_threshold=isosurface_threshold,
                    upsampling_factor=upsampling_factor)

plt.ioff()
plt.show()
