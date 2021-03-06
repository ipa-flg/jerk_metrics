#!/usr/bin/python

"""
Created on Jul 10, 2017

@author: flg-ma
@attention: Jerk Metric
@contact: marcel.albus@ipa.fraunhofer.de (Marcel Albus)
@version: 1.9.0
"""

import csv
import numpy as np
import pandas as pd
import rosbag_pandas as rp
import matplotlib.pyplot as plt
import sys
import listener
import time
from bcolors import TerminalColors as tc
import argparse
import os
import shutil


# AD stands for ArrayData
class AD(enumerate):
    TIME = 0  # time = '%time'
    HS = 1  # hs = 'field.header.seq'
    FHS = 2  # fhs = 'field.header.stamp'  # stamp for calculating differentiation
    VEL_X = 3  # velocity x-direction
    VEL_Y = 4  # velocity y-direction
    OME_Z = 5  # omega around z-axis
    POS_X = 6  # position x-axis
    POS_Y = 7  # position y-axis


# class for evaluating the jerk metrics
class JerkEvaluation:
    def __init__(self):
        # number counter for figures
        self.n = 1
        # smoothing parameter value [30 is good value]
        self.smo_para = 30
        self.timeformat = "%d_%m_%Y---%H:%M"

        # path where the data is saved
        self.dirpath = 'Data/' + time.strftime(self.timeformat)

        # save header names for further use
        self.time = '%time'
        self.hs = 'field.header.seq'
        self.fhs = 'field.header.stamp'  # stamp for calculating differentiation
        self.vel_x = 'field.twist.twist.linear.x'  # velocity x-direction
        self.vel_y = 'field.twist.twist.linear.y'  # velocity y-direction
        self.ome_z = 'field.twist.twist.angular.z'  # omega around z-axis
        self.pos_x = 'field.pose.pose.position.x'  # position x-axis
        self.pos_y = 'field.pose.pose.position.y'  # position y-axis
        # list for header-names from csv
        self.data = [self.time, self.hs, self.fhs, self.vel_x, self.vel_y, self.ome_z, self.pos_x, self.pos_y]

        # create array
        self.A = np.ones([0, 8], dtype=np.float64)

        self.A_grad_vel = np.ones([0, 8], dtype=np.float64)
        self.A_grad_vel_x = np.ones([0, 8], dtype=np.float64)
        self.A_grad_vel_y = np.ones([0, 8], dtype=np.float64)
        self.A_grad_vel_smo = np.ones([0, 8], dtype=np.float64)

        self.A_grad_acc = np.ones([0, 8], dtype=np.float64)
        self.A_grad_acc_x = np.ones([0, 8], dtype=np.float64)
        self.A_grad_acc_y = np.ones([0, 8], dtype=np.float64)
        self.A_grad_acc_smo = np.ones([0, 8], dtype=np.float64)
        self.A_grad_smo_acc = np.ones([0, 8], dtype=np.float64)

        self.A_grad_jerk = np.ones([0, 8], dtype=np.float64)
        self.A_grad_jerk_x = np.ones([0, 8], dtype=np.float64)
        self.A_grad_jerk_y = np.ones([0, 8], dtype=np.float64)
        self.A_grad_jerk_smo = np.ones([0, 8], dtype=np.float64)
        self.A_grad_smo_jerk = np.ones([0, 8], dtype=np.float64)

        self.A_diff = np.ones([0, 8], dtype=np.double)
        self.args = self.build_parser().parse_args()

    def build_parser(self):
        parser = argparse.ArgumentParser(
            description='Calculate jerk from a given topic publishing velocity. Standard: subscribe to topic \'/base/odometry_controller/odometry\'')
        # group = parser.add_mutually_exclusive_group()
        parser.add_argument('-j', '--jerk', help='max allowed jerk for jerk metrics, default = 4.0 [m/s^3]', type=float)
        parser.add_argument('-s', '--show_figures', action='store_true', help='show generated plots')
        parser.add_argument('-t', '--topic',
                            help='topic name to subscribe to, default: /base/odometry_controller/odometry', type=str,
                            default='/base/odometry_controller/odometry')
        parser.add_argument('-csv', '--load_csv', help='name and path to csv-file e.g.: \'~/test.csv\'', type=str,
                            default='Ingolstadt_Test3.csv')
        parser.add_argument('-bag', '--load_bag', help='name and path to bag-file e.g.: \'~/test.bag\'', type=str)
        parser.add_argument('-rc', '--read_csv', action='store_true', help='if flag is true a csv-file is read')
        parser.add_argument('-rb', '--read_bag', action='store_true', help='if flag is true a bag-file is read')
        # parser.add_argument('-rt', '--read_topic', action='store_true',
        #                    help='if flag is true it will be subscribed to given topic')
        # self.args = parser.parse_args()
        return parser

    # TODO: plot multiple data sets in one figure: e.g. bandwith and jerk data in one figure
    # plot data in one figure
    def plot1figure(self, xAxis, yAxis, legendLabel='legend label', xLabel='x-axis label', yLabel='y-axis label',
                    title='plot', axSize='auto', show=0):
        """
        :param xAxis: time axis data
        :param yAxis: data for y axis
        :param legendLabel: label name for first y-axis data (e.g. '$v_x$' for velocity in x-direction)
        :param xLabel: label for time axis (mostly 'Time [s]')
        :param yLabel: label for first y-axis (e.g. '$v [m/s]$', for given example above)
        :param title: title of the plot (obviously)
        :param axSize: 'auto' means min and max is chosen automatically, otherwise: [x_min, x_max, y_min, y_max]
        :param show: shall plot be shown? 1: yes / 2: no
        """
        if show == 1:
            plt.figure(self.n, figsize=(16.0, 10.0))
            plt.plot(xAxis, yAxis, 'r', label=legendLabel)
            plt.title(title, fontsize=20)
            plt.xlabel(xLabel, fontsize=20)
            plt.ylabel(yLabel, fontsize=20)
            plt.grid(True)

            if axSize != 'auto':
                plt.axis(axSize)

            plt.legend(fontsize=15)
            plt.savefig(
                self.dirpath + '/' + title.lower().replace(' ', '_') + '_' + time.strftime(self.timeformat) + '.pdf',
                bbox_inches='tight')

            # increment figure number counter
            self.n += 1
        else:
            pass

    # plot 2 subplots in one figure
    def plot2Subplots(self, xAxis, yAxis1, yAxis2, legendLabel1='first legend label',
                      legendLabel2='second legend label',
                      xLabel='x-axis label', yLabel1='y-axis label 1', yLabel2='y-axis label 2',
                      title='plot', axSize='auto', show=0):
        """
        @param xAxis: time axis array
        @param yAxis1: data for first y-axis as array
        @param yAxis2: data for second y-axis as array
        @param legendLabel1: label name for first y-axis data (e.g. '$v_x$' for velocity in x-direction)
        @param legendLabel2: label name for second y-axis data (e.g. '$v_y$' for velocity in y-direction)
        @param xLabel: label for time axis (mostly 'Time [s]')
        @param yLabel1: label for first y-axis (e.g. '$v [m/s]$', for given example above)
        @param yLabel2: label for second y-axis (e.g. '$v [m/s]$', for given example above)
        @param title: title of the plot (obviously)
        @param axSize: 'auto' means min and max is chosen automatically, otherwise: [x_min, x_max, y_min, y_max]
        @param show: shall plot be shown? 1: yes / 2: no
        @return: nothing
        """

        if show == 1:
            fig = plt.figure(self.n, figsize=(16.0, 10.0))
            # plt.subplot(211)
            ax1 = fig.add_subplot(211)
            plt.plot(xAxis, yAxis1, 'r', label=legendLabel1)
            plt.title(title, fontsize=20)
            plt.ylabel(yLabel1, fontsize=20)
            plt.grid(True)
            if axSize != 'auto':
                plt.axis(axSize)
            # legend: loc='best' sets legend to best location
            plt.legend()
            # plt.subplot(212)
            ax2 = fig.add_subplot(212)
            plt.plot(xAxis, yAxis2, 'g', label=legendLabel2)
            plt.xlabel(xLabel, fontsize=20)
            plt.ylabel(yLabel2, fontsize=20)
            plt.grid(True)
            if axSize != 'auto':
                plt.axis(axSize)
            # legend: loc='best' sets legend to best location
            plt.legend()
            self.annotate_max(xAxis, yAxis1, 'v', ax1)
            self.annotate_max(xAxis, yAxis2, 'j', ax2)
            plt.savefig(
                self.dirpath + '/' + title.lower().replace(' ', '_') + '_' + time.strftime(self.timeformat) + '.pdf',
                bbox_inches='tight')

            # increment figure number counter
            self.n += 1
        else:
            pass

    def annotate_max(self, x, y, unit, ax=None):
        '''
        adds a text-box to the plot with the max value for 'j' or 'v' printed out, form: 't=x, v=x'
        :param x: x-axis values
        :param y: y-axis values
        :param unit: defines the unit of the plot, i.e. 'v' or 'j'
        :param ax: plot axis on which the text box is added
        '''
        xmax = x[np.argmax(y)]
        ymax = y.max()
        x_max_string = '{:.3f}'.format(xmax)
        y_max_string = '{:.3f}'.format(ymax)
        text = '$\mathrm{t}=' + x_max_string + ',\;' + '\mathrm{' + unit + '_{max}}=' + y_max_string + '$'
        if not ax:
            ax = plt.gca()
        bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
        # arrowprops = dict(arrowstyle="->", connectionstyle="angle,angleA=0,angleB=60")
        # kw = dict(xycoords='data', textcoords="axes fraction",
        #           arrowprops=arrowprops, bbox=bbox_props, ha="right", va="top")
        kw = dict(xycoords='data', textcoords="axes fraction",
                  bbox=bbox_props, ha="left", va="top", size='x-large')
        ax.annotate(text, xy=(xmax, ymax), xytext=(0.01, 0.96), **kw)

    # plot the specified figures
    def show_figures(self):
        # plot position
        self.plot2Subplots(self.A[:, AD.FHS], self.A[:, AD.POS_X], self.A[:, AD.POS_Y],
                           '$\mathrm{Pos_x}$', '$\mathrm{Pos_y}$', 'Time [s]', '$\mathrm{x\;[m]}$',
                           '$\mathrm{y\;[m]}$', 'Position', axSize='auto', show=0)

        # plot velocity odometry controller
        self.plot2Subplots(self.A[:, AD.FHS], self.A[:, AD.VEL_X], self.A[:, AD.VEL_Y],
                           '$\mathrm{v_x}$', '$\mathrm{v_y}$', 'Time [s]', '$\mathrm{v\;[m/s]}$', '$\mathrm{v\;[m/s]}$',
                           title='Velocity', show=0)

        # plot velocity (x^2+y^2)^0.5 diff
        self.plot2Subplots(self.A[:-1, AD.FHS], np.sqrt(self.A_diff[:, AD.POS_X] ** 2 + self.A_diff[:, AD.POS_Y] ** 2),
                           np.sqrt(self.A[:-1, AD.VEL_X] ** 2 + self.A[:-1, AD.VEL_Y] ** 2),
                           '$\mathrm{v_{x,diff,root}}$', '$\mathrm{v_{x,odo,root}}$', 'Time [s]', '$\mathrm{v\;[m/s]}$',
                           '$\mathrm{v\;[m/s]}$', title='Velocity calculated using \'diff\'', show=0)

        # plot velocity (x^2+y^2)^0.5 gradient
        self.plot2Subplots(self.A[:, AD.FHS], self.A_grad_vel[:, ],
                           np.sqrt(self.A[:, AD.VEL_X] ** 2 + self.A[:, AD.VEL_Y] ** 2),
                           '$\mathrm{v_{x,grad,root}}$', '$\mathrm{v_x{x,odo,root}}$', 'Time [s]',
                           '$\mathrm{v\;[m/s]}$', '$\mathrm{v\;[m/s]}$', title='Velocity calculated using \'gradient\'',
                           axSize=[0, 73, -.05, .3], show=0)

        # plot acceleration diff: x,y
        self.plot2Subplots(self.A[:-1, AD.FHS], self.A_diff[:, AD.VEL_X], self.A_diff[:, AD.VEL_Y],
                           '$a_x$', '$a_y$', 'Time [s]', '$\mathrm{a\;[m/s^2]}$', '$\mathrm{a\;[m/s^2]}$',
                           'Acceleration', axSize='auto', show=0)

        # plot diff and gradient method comparison for acceleration
        self.plot2Subplots(self.A[:-1, AD.FHS], self.A_grad_acc[:-1, ],
                           np.sqrt(self.A_diff[:, AD.VEL_X] ** 2 + self.A_diff[:, AD.VEL_Y] ** 2),
                           '$\mathrm{a_{grad}}$', '$\mathrm{a_{diff}}$', 'Time [s]', '$\mathrm{a\;[m/s^2]}$',
                           '$\mathrm{a\;[m/s^2]}$', 'Diff_Grad', axSize='auto', show=0)

        # plot acceleration smoothed and noisy signal
        self.plot2Subplots(self.A[:, AD.FHS], self.A_grad_acc_smo[:, ],
                           self.A_grad_acc[:, ], '$\mathrm{a_{grad,smoothed}}$', '$\mathrm{a_{grad,noisy}}$',
                           'Time [s]', '$\mathrm{a\;[m/s^2]}$', '$\mathrm{a\;[m/s^2]}$',
                           'Acceleration', axSize=[0, 80, -.1, 1.0], show=0)

        # plot acceleration x,y separately
        self.plot2Subplots(self.A[:, AD.FHS], self.A_grad_acc_x, self.A_grad_acc_y, '$a_{grad,x}$', '$a_{grad,y}$',
                           'Time [s]', '$\mathrm{a\;[m/s^2]}$', '$\mathrm{a\;[m/s^2]}$',
                           title='Acceleration: x,y direction', show=0)

        # plot jerk smoothed and noisy: 30 is good value for smoothing
        self.plot2Subplots(self.A[:, AD.FHS], self.A_grad_smo_jerk[:, ],
                           self.A_grad_jerk[:, ], '$\mathrm{j_{grad,smooth}}$', '$\mathrm{j_{grad,noisy}}$',
                           'Time [s]', '$\mathrm{j\;[m/s^3]}$', '$\mathrm{j\;[m/s^3]}$',
                           'Jerk', axSize=[0, 80, -.5, 15], show=0)

        # plot complete jerk smoothed
        self.plot1figure(self.A[:, AD.FHS], self.A_grad_smo_jerk,
                         '$\mathrm{j_{smooth,30}}$', 'Time [s]', '$\mathrm{j\;[m/s^3]}$', 'Jerk Smoothed',
                         axSize='auto', show=1)

        # plot velocity and jerk
        self.plot2Subplots(self.A[:, AD.FHS], np.sqrt(self.A[:, AD.VEL_X] ** 2 + self.A[:, AD.VEL_Y] ** 2),
                           self.A_grad_smo_jerk, '$\mathrm{v_{A}}$', '$\mathrm{j_{smooth,30}}$', 'Time [s]',
                           '$\mathrm{v\;[m/s]}$', '$\mathrm{j\;[m/s^3]}$', 'Velocity and Jerk', show=1)

        # files are saved but not shown directly when program is executed
        # plt.show()

    # plot smoothing comparison between 1x and 2x smoothing
    def smoothing_times_plot(self):
        plt.figure(self.n, figsize=(16.0, 10.0))
        plt.plot(self.A[:, AD.TIME], self.A[:, AD.VEL_X], 'r',
                 label='$v_{normal}$')
        plt.plot(self.A[:, AD.TIME], self.smooth(self.A[:, AD.VEL_X], 30, window='hanning'),
                 label='$v_{smooth,1\,times}$')
        plt.plot(self.A[:, AD.TIME], self.smooth(
            self.smooth(self.A[:, AD.VEL_X], 10, window='hanning'),
            50, window='hamming'), label='$v_{smooth,2\,times}$')
        plt.grid(True)
        plt.xlabel('Time [s]', fontsize=20)
        plt.ylabel('$\mathrm{v\;[m/s3]}$', fontsize=20)
        plt.title('Smoothing Comparison', fontsize=20)
        plt.legend(fontsize=15)
        plt.savefig('smoothing_plot.pdf', bbox_inches='tight')

        # increment figure counter
        self.n += 1

    # plot jerk comparison between smoothed and noisy signal
    def jerk_comparison(self):
        plt.figure(self.n, figsize=(16.0, 10.0))
        for i in [10, 20, 30, 40, 50]:
            plt.plot(self.A[:, AD.FHS], self.smooth(self.A_grad_jerk[:, ], i, window='hanning'),
                     label='$\mathrm{j_{grad,smooth,' + str(i) + '}}$')
            plt.xlabel('Time [s]', fontsize=20)
            plt.ylabel('$\mathrm{j\;[m/s^3]}$', fontsize=20)
            plt.grid(True)

        plt.plot(self.A[:, AD.FHS], self.bandwidth(4.5), 'k--', label='$\mathrm{Bandwidth}$')
        plt.title('Jerk comparison different smoothing', fontsize=20)
        plt.legend(fontsize=15)
        plt.axis([18, 23, -.5, 7])
        plt.draw()
        plt.savefig('jerk_comparison.pdf', bbox_inches='tight')

        # increment figure counter
        self.n += 1

    def smooth(self, x, window_len=11, window='hanning'):
        """smooth the data using a window with requested size.

        This method is based on the convolution of a scaled window with the signal.
        The signal is prepared by introducing reflected copies of the signal
        (with the window size) in both ends so that transient parts are minimized
        in the begining and end part of the output signal.

        input:
            x: the input signal
            window_len: the dimension of the smoothing window; should be an odd integer
            window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
                flat window will produce a moving average smoothing.

        output:
            the smoothed signal

        example:

        t=linspace(-2,2,0.1)
        x=sin(t)+randn(len(t))*0.1
        y=smooth(x)

        see also:

        numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
        scipy.signal.lfilter

        TODO: the window parameter could be the window itself if an array instead of a string
        NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
        """

        if x.ndim != 1:
            raise ValueError, "smooth only accepts 1 dimension arrays."

        if x.size < window_len:
            raise ValueError, "Input vector needs to be bigger than window size."

        if window_len < 3:
            return x

        if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
            raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"

        s = np.r_[x[window_len - 1:0:-1], x, x[-2:-window_len - 1:-1]]
        # print(len(s))
        if window == 'flat':  # moving average
            w = np.ones(window_len, 'd')
        else:
            w = eval('np.' + window + '(window_len)')

        y = np.convolve(w / w.sum(), s, mode='valid')

        return y[(window_len / 2 - 1):-(window_len / 2)]
        # return y

    # read data from .csv-file
    def read_data_csv(self, filename):
        '''
        read data from a given csv-file
        :param filename: path to csv-file
        :return: --
        '''
        # global A
        global m_A
        global n_A

        with open(filename, 'rb') as csvfile:
            odometry_reader = csv.DictReader(csvfile, delimiter=',')
            # column_names_csv is of type 'list'
            column_names_csv = odometry_reader.fieldnames
            # get number of rows in csv-file
            row_number = sum(1 for line in odometry_reader)
            A = np.zeros([row_number, self.data.__len__()], dtype=np.float64)
            # set pointer to first row
            csvfile.seek(0)
            # jump over first now with names
            odometry_reader.next()

            i = 0
            for row in odometry_reader:
                # jump over header row with names
                if row[self.data[0]] == self.time:
                    continue
                j = 0
                for name in self.data:
                    if name == self.time or name == self.fhs:
                        # scale time and field.header.stamp with factor 1e-9
                        scale = 10 ** -9
                    else:
                        # otherwise no scaling is needed
                        scale = 1
                    a = row[name]
                    A[i, j] = float(a) * scale
                    j += 1
                i += 1

        # set time to start at 0s
        A[:, AD.TIME] = A[:, AD.TIME] - A[0, AD.TIME]
        A[:, AD.FHS] = A[:, AD.FHS] - A[0, AD.FHS]
        # see whether scaling was wrong or not
        if A[-1, AD.FHS] - A[0, AD.FHS] < 0.1:
            A[:, AD.FHS] = A[:, AD.FHS] * 10 ** 9
        # save dimensions of A
        m_A, n_A = A.shape

        # print 'Time of Interval: {:.3f} [s]'.format(A[-1, AD.TIME] - A[0, AD.TIME])
        print 'Time of Interval: {:.3f} [s]'.format(A[-1, AD.FHS] - A[0, AD.FHS])
        self.A = A

    def read_data_subscriber(self, topic):
        '''
        read data from a topic and save it in array
        :param topic: topic to read data from
        :return: --
        '''
        # global A
        global m_A
        global n_A

        # instantiate class NodeListener
        if topic is not None:
            nl = listener.NodeListener(topic)
        else:
            nl = listener.NodeListener()
        # subscribe to odometry
        nl.listener()
        self.A = np.array(nl.return_array())
        print tc.OKBLUE + '=' * 25 + tc.ENDC
        print tc.OKBLUE + 'Got this array: ', self.A.shape, tc.ENDC
        print tc.OKBLUE + '=' * 25 + tc.ENDC

        # set time to start at 0s
        self.A[:, AD.FHS] = self.A[:, AD.FHS] - self.A[0, AD.FHS]
        # save dimensions of A
        m_A, n_A = self.A.shape

        print 'Time of Interval: {:.4f} [s]'.format(self.A[-1, AD.FHS] - self.A[0, AD.FHS])

    # read data directly from a bagfile
    def read_data_bagfile(self, bagname, exclude=None, include='/base/odometry_controller/odometry'):
        '''
        read data from a bagfile generated with ros
        :param bagname: path to bagfile
        :param exclude: exclude topics (regular expression possible)
        :param include: include topics (regular expression possible)
        :return: --
        '''
        global m_A
        global n_A

        df = rp.bag_to_dataframe(bagname, include=include, exclude=exclude, seconds=True)

        fieldnames = []
        for dat in self.data:
            inc = include[1:] + '__'
            fieldnames.append((inc.replace('/', '_') + dat[6:]).replace('.', '_'))
        fieldnames[2] = 'index'

        # save fieldnames from dataframe to matrix A
        A = df.reset_index()[[fieldnames[i] for i in xrange(2, fieldnames.__len__())]].as_matrix()
        # dummy data for '%time' and 'field.header.stamp', because both are not necessary
        B = np.ones([A.shape[0], 2])
        # put data matrix A and dummy matrix B together
        A = np.concatenate((B, A), axis=1)
        # set time to start at 0s
        A[:, AD.FHS] = A[:, AD.FHS] - A[0, AD.FHS]

        m_A, n_A = A.shape
        self.A = A
        print 'Time of Interval: {:.4f} [s]'.format(self.A[-1, AD.FHS] - self.A[0, AD.FHS])

    # get differentiation from given data
    def differentiation(self):
        # # global A_grad_vel
        # global A_grad_vel_smo
        # # global A_grad_vel_x
        # # global A_grad_vel_y
        # global A_grad_acc
        # global A_grad_acc_smo
        # # global A_grad_acc_x
        # # global A_grad_acc_y
        # global A_grad_jerk
        # global A_grad_jerk_smo
        # # global A_grad_jerk_x
        # # global A_grad_jerk_y
        #
        # # global A_diff
        #
        # global A_grad_smo_acc
        # global A_grad_smo_jerk

        # differentiation
        self.A_grad_vel_x = np.gradient(self.A[:, AD.POS_X], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        self.A_grad_vel_y = np.gradient(self.A[:, AD.POS_Y], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        # (x^2+y^2)^0.5 to get absolut velocity
        self.A_grad_vel = np.sqrt(self.A_grad_vel_x[:, ] ** 2 + self.A_grad_vel_y[:, ] ** 2)
        self.A_grad_vel_smo = self.smooth(self.A_grad_vel[:, ], self.smo_para, window='hanning')

        # differentiation
        # compute acceleration from velocity by differentiation
        self.A_grad_acc_x = np.gradient(self.A[:, AD.VEL_X], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        self.A_grad_acc_y = np.gradient(self.A[:, AD.VEL_Y], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        # (x^2+y^2)^0.5 to get absolute acceleration
        self.A_grad_acc = np.sqrt(self.A_grad_acc_x[:, ] ** 2 + self.A_grad_acc_y[:, ] ** 2)
        # smoothed after differentiation
        self.A_grad_acc_smo = self.smooth(self.A_grad_acc[:, ], self.smo_para, window='hanning')
        # smoothed acc used for (x^2+y^2)^0.5 to get absolute acceleration
        self.A_grad_smo_acc = np.sqrt(self.smooth(self.A_grad_acc_x[:, ], 30, window='hanning') ** 2 +
                                      self.smooth(self.A_grad_acc_y[:, ], 30, window='hanning') ** 2)

        # differentiation
        # compute jerk from acceleration by differentiation
        self.A_grad_jerk_x = np.gradient(self.A_grad_acc_x[:, ], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        self.A_grad_smo_jerk_x = np.gradient(self.smooth(self.A_grad_acc_x[:, ], 30, window='hanning'),
                                             self.A[1, AD.FHS] - self.A[0, AD.FHS])
        # noisy acc used for differentiation
        self.A_grad_jerk_y = np.gradient(self.A_grad_acc_y[:, ], self.A[1, AD.FHS] - self.A[0, AD.FHS])
        # smoothed acc used for differentiation
        self.A_grad_smo_jerk_y = np.gradient(self.smooth(self.A_grad_acc_y[:, ], 30, window='hanning'),
                                             self.A[1, AD.FHS] - self.A[0, AD.FHS])
        # (x^2+y^2)^0.5 to get absolut jerk
        self.A_grad_jerk = np.sqrt(self.A_grad_jerk_x[:, ] ** 2 + self.A_grad_jerk_y[:, ] ** 2)
        # smoothed after differentiation
        self.A_grad_jerk_smo = self.smooth(self.A_grad_jerk[:, ], 30, window='hanning')
        # smoothed acc used for differentiation
        self.A_grad_smo_jerk = np.sqrt(self.A_grad_smo_jerk_x[:, ] ** 2 + self.A_grad_smo_jerk_y[:, ] ** 2)

        # differentiation using diff
        self.A_diff = np.diff(np.transpose(self.A))
        self.A_diff = np.transpose(self.A_diff)

    def save_csv(self):
        print 'Date: ' + time.strftime(self.timeformat)

        # C_jerk = np.concatenate(([['jerk']], self.A_grad_smo_jerk.reshape(self.A_grad_smo_jerk.__len__(), 1)), axis=0)
        # C_acc = np.concatenate(([['acc']], self.A_grad_smo_acc.reshape(self.A_grad_smo_acc.__len__(), 1)), axis=0)

        data_matrix = np.array([self.data[i] for i in xrange(0, self.data.__len__())])

        df_A = pd.DataFrame(data=self.A, columns=data_matrix)
        df_smo_acc = pd.DataFrame({'smo_acc': self.A_grad_smo_acc})
        df_smo_jerk = pd.DataFrame({'smo_jerk': self.A_grad_smo_jerk})

        B = pd.concat([df_A, df_smo_acc.smo_acc, df_smo_jerk.smo_jerk], axis=1)

        if os.path.exists(self.dirpath):
            for i in xrange(1, 100):
                if os.path.exists(self.dirpath + '__' + str(i)):
                    continue
                else:
                    filepath = self.dirpath + '__' + str(i)
                    os.mkdir(filepath)
                    self.dirpath = filepath
                    break
        else:
            os.mkdir(self.dirpath)
            filepath = self.dirpath

        # copy bagfile in created folder together with saved .csv-file
        if self.args.read_bag:
            shutil.copy2(self.args.load_bag, filepath)

        B.to_csv(filepath + '/' + time.strftime(self.timeformat) + '_' + str(
            '{:.3f}'.format(self.A[-1, AD.FHS] - self.A[0, AD.FHS])) + '.csv', sep=',')

    # creating bandwidth matrix
    def bandwidth(self, max):
        B = np.zeros([m_A, 1])
        for i in xrange(0, m_A):
            B[i, 0] = max
        return B

    # compare jerk with given max bandwidth, if jerk is to big function returns false
    def jerk_metrics(self, max_jerk):
        '''
        jerk metrics to see if max jerk is in desired range
        :param max_jerk: max allowed jerk for comparison
        :return: false - jerk is above max allowed jerk
        :return: true - jerk is below max allowed jerk
        '''
        for i in xrange(0, m_A):
            if self.A_grad_smo_jerk[i,] >= max_jerk:
                output = tc.FAIL + 'Jerk: {:.3f} [m/s^3] at time: {:.6f} [s] with index [{}] is bigger than max allowed jerk: {:.3f} [m/s^3]' + tc.ENDC
                print tc.FAIL + '=' * (output.__len__() - 6) + tc.ENDC
                print output.format(self.A_grad_smo_jerk[i,], self.A[i, AD.FHS], i, max_jerk)
                print 'Jerk below: {:.3f} [m/s^3] at time: {:.3f} [s] is in range'.format(self.A_grad_smo_jerk[i - 1,],
                                                                                          self.A[i - 1, AD.FHS])
                print 'Max Jerk: {:.4f} [m/s^3] at index [{}]'.format(self.A_grad_smo_jerk.max(),
                                                                      np.argmax(self.A_grad_smo_jerk))
                print tc.FAIL + '=' * (output.__len__() - 6) + tc.ENDC
                return False
        print tc.OKGREEN + '=' * 25 + tc.ENDC
        print tc.OKGREEN + 'Jerk is in desired range!' + tc.ENDC
        print 'Max Jerk: {:.4f} [m/s^3]'.format(self.A_grad_smo_jerk.max())
        print tc.OKGREEN + '=' * 25 + tc.ENDC
        return True

    # smoothing in workflow comparison
    def smoothing_workflow_comparison(self):
        plt.figure(self.n, figsize=(16.0, 10.0))
        plt.subplot(211)
        plt.plot(self.A[:, AD.TIME], self.A_grad_acc, 'b', label='unsmoothed')
        plt.plot(self.A[:, AD.TIME], self.A_grad_acc_smo, 'k', label='smoothed after differentiation')
        plt.plot(self.A[:, AD.TIME], self.A_grad_smo_acc, 'r', label='smoothed acc x and y used')
        plt.ylabel('$\mathrm{a\;[m/s^2]}$$', fontsize=20)
        plt.legend()
        plt.grid(True)

        plt.subplot(212)
        plt.plot(self.A[:, AD.TIME], self.A_grad_jerk, 'b', label='unsmoothed')
        plt.plot(self.A[:, AD.TIME], self.A_grad_jerk_smo, 'k', label='smoothed after differentiation')
        plt.plot(self.A[:, AD.TIME], self.A_grad_smo_jerk, 'r', label='smoothed acc used for differentiation')
        plt.ylabel('$\mathrm{j\;[m/s^3]}$', fontsize=20)
        plt.grid(True)

        plt.xlabel('Time [s]', fontsize=20)
        plt.legend()
        plt.draw()
        plt.savefig('smoothing_in_workflow_comparison.pdf', bbox_inches='tight')
        self.n += 1

    # calling the other functions
    def main(self):
        # close all existing figures
        plt.close('all')

        # either read given csv-file...
        if self.args.read_csv:
            print tc.OKBLUE + '=' * (17 + len(self.args.load_csv))
            print 'read csv-file: \'{}\''.format(self.args.load_csv)
            print '=' * (17 + len(self.args.load_csv)) + tc.ENDC
            self.read_data_csv(self.args.load_csv)

        # ... or given bagfile...
        elif self.args.read_bag:
            print tc.OKBLUE + '=' * (17 + len(self.args.load_bag))
            print 'read bag-file: \'{}\''.format(self.args.load_bag)
            print '=' * (17 + len(self.args.load_bag)) + tc.ENDC
            self.read_data_bagfile(self.args.load_bag)


        # ...or read given topic
        else:
            # if self.args.read_topic:
            print tc.OKBLUE + '=' * (22 + len(self.args.topic))
            print 'subscribe to topic: \'{}\''.format(self.args.topic)
            print '=' * (22 + len(self.args.topic)) + tc.ENDC
            self.read_data_subscriber(self.args.topic)

        # print tc.OKBLUE + '=' * (17 + len(self.args.load_csv))
        # print 'read csv-file: \'{}\''.format(self.args.load_csv)
        # print '=' * (17 + len(self.args.load_csv)) + tc.ENDC
        # self.read_data_csv(self.args.load_csv)

        self.differentiation()
        self.save_csv()

        # if jerk value is defined use it
        if self.args.jerk is not None:
            self.jerk_metrics(self.args.jerk)
        else:
            self.jerk_metrics(4.0)

        # smoothing_times_plot()
        # smoothing_workflow_comparison()
        # self.jerk_comparison()

        # show figures
        if self.args.show_figures:
            je.show_figures()


# commandline input: --jerk *max_jerk* or -j *max_jerk*
# if no commandline input is given, max_jerk=4.0 is set
if __name__ == '__main__':
    je = JerkEvaluation()
    je.main()

pass
