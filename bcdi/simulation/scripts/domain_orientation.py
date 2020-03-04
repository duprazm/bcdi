# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-present : DESY PHOTON SCIENCE
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

import numpy as np
from matplotlib import pyplot as plt
from scipy import signal
import tkinter as tk
from tkinter import filedialog
import sys
sys.path.append('C:/Users/Jerome/Documents/myscripts/bcdi/')
import bcdi.graph.graph_utils as gu
import bcdi.experiment.experiment_utils as exp
import bcdi.postprocessing.postprocessing_utils as pu
import bcdi.simulation.simulation_utils as simu

helptext = """
Calculate the position of the Bragg peaks for a mesocrystal given the lattice type, the unit cell parameter
and beamline-related parameters. Assign 3D Gaussians to each lattice point and rotates the unit cell in order to
maximize the cross-correlation of the simulated data with experimental data.

Laboratory frame convention (CXI): z downstream, y vertical up, x outboard."""

datadir = "D:/data/P10_August2019/data/gold2_2_00515/pynx/441_486_441_1_4_4/"
savedir = "D:/data/P10_August2019/data/gold2_2_00515/simu/"
################
# sample setup #
################
unitcell = 'fcc'
unitcell_param = 22.4  # in nm, unit cell parameter
#########################
# unit cell orientation #
#########################
angles_ranges = [0, 90, 0, 90, 0, 90]  # in degrees, ranges to span for the rotation around qx downstream,
# qz vertical up and qy outboard respectively: [start, stop, start, stop, start, stop]    stop is excluded
angular_step = 2  # in degrees
angles = [1, 20, 0]  # in degrees, rotation around qx downstream, qz vertical up and qy outboard respectively
#######################
# beamline parameters #
#######################
sdd = 4.95  # in m, sample to detector distance
energy = 8700  # in ev X-ray energy
##################
# detector setup #
##################
detector = "Eiger4M"  # "Eiger2M" or "Maxipix" or "Eiger4M"
direct_beam = (1195, 1187)  # tuple of int (vertical, horizontal): position of the direct beam in pixels
# this parameter is important for gridding the data onto the laboratory frame
roi_detector = [direct_beam[0] - 972, direct_beam[0] + 972, direct_beam[1] - 883, direct_beam[1] + 883]
# [Vstart, Vstop, Hstart, Hstop]
binning = [4, 4, 4]  # binning of the detector
###########
# options #
###########
kernel_length = 21  # width of the 3D gaussian window
debug = False  # True to see more plots
##################################
# end of user-defined parameters #
##################################

#######################
# Initialize detector #
#######################
detector = exp.Detector(name=detector, binning=binning, roi=roi_detector)

nbz, nby, nbx = int(np.floor((detector.roi[3] - detector.roi[2]) / detector.binning[2])), \
                   int(np.floor((detector.roi[1] - detector.roi[0]) / detector.binning[1])), \
                   int(np.floor((detector.roi[3] - detector.roi[2]) / detector.binning[2]))
# for P10 data the rotation is around y vertical, hence gridded data range & binning in z and x are identical

###################
# define colormap #
###################
bad_color = '1.0'  # white background
colormap = gu.Colormap(bad_color=bad_color)
my_cmap = colormap.cmap
plt.ion()

##########################
# load experimental data #
##########################
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(initialdir=datadir, title="Select the data to fit",
                                       filetypes=[("NPZ", "*.npz")])
data = np.load(file_path)['data']

#####################################
# define the list of angles to test #
#####################################
angles_qx = np.arange(start=angles_ranges[0], stop=angles_ranges[1], step=angular_step)
angles_qz = np.arange(start=angles_ranges[2], stop=angles_ranges[3], step=angular_step)
angles_qy = np.arange(start=angles_ranges[4], stop=angles_ranges[5], step=angular_step)

cross_corr = np.zeros((len(angles_qx), len(angles_qz), len(angles_qy)))

for idz, alpha in enumerate(angles_qx):
    for idy, beta in enumerate(angles_qz):
        for idx, gamma in enumerate(angles_qy):

            ######################
            # create the lattice #
            ######################
            pivot, q_values, lattice, peaks = simu.lattice(energy=energy, sdd=sdd, direct_beam=direct_beam,
                                                           detector=detector, unitcell=unitcell,
                                                           unitcell_param=unitcell_param, euler_angles=angles)
            # peaks in the format [[h, l, k], ...]: CXI convention downstream , vertical up, outboard
            struct_array = np.zeros((nbz, nby, nbx))
            for [piz, piy, pix] in lattice:
                struct_array[piz, piy, pix] = 1

            ##############################################
            # convolute the lattice with a 3D peak shape #
            ##############################################
            # since we have a small list of peaks, do not use convolution (too slow) but for loop
            peak_shape = pu.gaussian_kernel(ndim=3, kernel_length=kernel_length, sigma=3, debugging=False)
            maxpeak = peak_shape.max()

            for [piz, piy, pix] in lattice:
                startz1, startz2 = max(0, int(piz-kernel_length//2)), -min(0, int(piz-kernel_length//2))
                stopz1, stopz2 = min(nbz-1, int(piz+kernel_length//2)),\
                    kernel_length + min(0, int(nbz-1 - (piz+kernel_length//2)))
                starty1, starty2 = max(0, int(piy-kernel_length//2)), -min(0, int(piy-kernel_length//2))
                stopy1, stopy2 = min(nby-1, int(piy+kernel_length//2)),\
                    kernel_length + min(0, int(nby-1 - (piy+kernel_length//2)))
                startx1, startx2 = max(0, int(pix-kernel_length//2)), -min(0, int(pix-kernel_length//2))
                stopx1, stopx2 = min(nbx-1, int(pix+kernel_length//2)),\
                    kernel_length + min(0, int(nbx-1 - (pix+kernel_length//2)))
                struct_array[startz1:stopz1+1, starty1:stopy1+1, startx1:stopx1+1] =\
                    peak_shape[startz2:stopz2, starty2:stopy2, startx2:stopx2]

            # mask the region near the origin of the reciprocal space
            struct_array[pivot[0] - kernel_length // 2:pivot[0] + kernel_length // 2 + 1,
                         pivot[1] - kernel_length // 2:pivot[1] + kernel_length // 2 + 1,
                         pivot[2] - kernel_length // 2:pivot[2] + kernel_length // 2 + 1] = 0

            ##########################################################
            # calculate the cross-correlation with experimental data #
            ##########################################################
            # Do an array flipped convolution, which is a correlation.
            cross_corr[idz, idy, idx] = signal.fftconvolve(data, struct_array[::-1, ::-1, ::-1], mode='same').sum()

###############
# plot result #
###############
vmin = cross_corr.min()
vmax = cross_corr.max()
fig, _, _ = gu.multislices_plot(cross_corr, sum_frames=True, title='Cross-correlation', vmin=vmin,
                                vmax=vmax, plot_colorbar=True, cmap=my_cmap, is_orthogonal=True,
                                reciprocal_space=False)
fig.text(0.60, 0.25, "Kernel size = " + str(kernel_length) + " pixels", size=12)
plt.pause(0.1)
plt.savefig(savedir + 'cross_corr.png')
plt.ioff()
plt.show()
