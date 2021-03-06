# -*- coding: utf-8 -*-
# Lindley Graham 3/10/2014
"""
This module contains functions for adaptive random sampling. We assume we are
given access to a model, a parameter space, and a data space. The model is a
map from the paramter space to the data space. We desire to build up a set of
samples to solve an inverse problem thus giving us information about the
inverse mapping. Each sample consists of a parameter coordinate, data
coordinate pairing. We assume the measure of both spaces is Lebesgue.

We employ an approach based on using multiple sample chains.
"""

import numpy as np
import scipy.io as sio
import bet.sampling.basicSampling as bsam
import math, os
from bet.Comm import *

size = comm.Get_size()
rank = comm.Get_rank()

def loadmat(save_file, lb_model=None):
    """
    Loads data from ``save_file`` into a
    :class:`~bet.sampling.adaptiveSampling.sampler` object.

    :param string save_file: file name
    :param model: runs the model at a given set of parameter samples and
        returns data 
    :rtype: tuple
    :returns: (sampler, samples, data)

    """
    # load the data from a *.mat file
    mdat = sio.loadmat(save_file)
    # load the samples
    if mdat.has_key('samples'):
        samples = mdat['samples']
    else:
        samples = None
    # load the data
    if mdat.has_key('data'):
        data = mdat['data']
    else:
        data = None
    # recreate the sampler
    new_sampler = sampler(mdat['num_samples'], mdat['chain_length'],
            lb_model)
    
    return (new_sampler, samples, data)

class sampler(bsam.sampler):
    """
    This class provides methods for adaptive sampling of parameter space to
    provide samples to be used by algorithms to solve inverse problems. 
    
    chain_length
        number of batches of samples
    num_chains
        number of samples per batch (either a single int or a list of int)
    lb_model
        :class:`~bet.loadBalance.load_balance` runs the model at a given set of
        parameter samples and returns data """
    def __init__(self, num_samples, chain_length, lb_model):
        """
        Initialization
        """
        super(sampler, self).__init__(lb_model, num_samples)
        self.chain_length = chain_length
        self.num_chains_pproc = int(math.ceil(num_samples/float(chain_length*size)))
        self.num_chains = size * self.num_chains_pproc
        self.num_samples = chain_length * self.num_chains
        self.lb_model = lb_model
        self.sample_batch_no = np.repeat(range(self.num_chains), chain_length,
                0)

    def update_mdict(self, mdict):
        """
        Set up references for ``mdict``

        :param dict() mdict: dictonary of sampler parameters

        """
        super(sampler, self).update_mdict(mdict)
        mdict['chain_length'] = self.chain_length
        mdict['num_chains'] = self.num_chains
        mdict['sample_batch_no'] = self.sample_batch_no
        
    def run_gen(self, kern_list, rho_D, maximum, param_min, param_max,
            t_kernel, savefile, initial_sample_type="lhs", criterion='center'):
        """
        Generates samples using generalized chains and a list of different
        kernels.

        :param list() kern_list: List of kernels.
        :param rho_D: probability density on D
        :type rho_D: callable function that takes a :class:`np.array` and
            returns a :class:`numpy.ndarray`
        :param double maximum: maximum value of rho_D
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kernel: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
         :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :rtype: tuple
        :returns: ((samples, data), all_step_ratios, num_high_prob_samples,
            sorted_incidices_of_num_high_prob_samples, average_step_ratio)

        """
        # generalized chains
        results = list()
        r_step_size = list()
        results_rD = list()
        mean_ss = list()
        for kern in kern_list:
            (samples, data, step_sizes) = self.generalized_chains(
                    param_min, param_max, t_kernel, kern, savefile,
                    initial_sample_type, criterion)
            results.append((samples, data))
            r_step_size.append(step_sizes)
            results_rD.append(int(sum(rho_D(data)/maximum)))
            mean_ss.append(np.mean(step_sizes))
        sort_ind = np.argsort(results_rD)
        return (results, r_step_size, results_rD, sort_ind, mean_ss)

    def run_reseed(self, kern_list, rho_D, maximum, param_min, param_max,
            t_kernel, savefile, initial_sample_type="lhs", criterion='center',
            reseed=3):
        """
        Generates samples using reseeded chains and a list of different
        kernels.

        THIS IS NOT OPERATIONAL DO NOT USE.

        :param list() kern_list: List of kernels.
        :param rho_D: probability density on D
        :type rho_D: callable function that takes a :class:`np.array` and
            returns a :class:`numpy.ndarray`
        :param double maximum: maximum value of rho_D
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kernel: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
         :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :rtype: tuple
        :returns: ((samples, data), all_step_ratios, num_high_prob_samples,
            sorted_incidices_of_num_high_prob_samples, average_step_ratio)

        """
        results = list()
        # reseeding sampling
        results = list()
        r_step_size = list()
        results_rD = list()
        mean_ss = list()
        for kern in kern_list:
            (samples, data, step_sizes) = self.reseed_chains(
                    param_min, param_max, t_kernel, kern, savefile,
                    initial_sample_type, criterion, reseed)
            results.append((samples, data))
            r_step_size.append(step_sizes)
            results_rD.append(int(sum(rho_D(data)/maximum)))
            mean_ss.append(np.mean(step_sizes))
        sort_ind = np.argsort(results_rD)
        return (results, r_step_size, results_rD, sort_ind, mean_ss)

    def run_tk(self, init_ratio, min_ratio, max_ratio, rho_D, maximum,
            param_min, param_max, kernel, savefile,
            initial_sample_type="lhs", criterion='center'):
        """
        Generates samples using generalized chains and
        :class:`~bet.sampling.transition_set` created using
        the `init_ratio`, `min_ratio`, and `max_ratio` parameters.
    
        :param list() init_ratio: Initial step size ratio compared to the
            parameter domain.
        :param list() min_ratio: Minimum step size compared to the initial step
            size.
        :param list() max_ratio: Maximum step size compared to the maximum step
            size.
        :param rho_D: probability density on D
        :type rho_D: callable function that takes a :class:`np.array` and
            returns a :class:`numpy.ndarray`
        :param double maximum: maximum value of rho_D
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kernel: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
         :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :rtype: tuple
        :returns: ((samples, data), all_step_ratios, num_high_prob_samples,
            sorted_incidices_of_num_high_prob_samples, average_step_ratio)

        """
        results = list()
        r_step_size = list()
        results_rD = list()
        mean_ss = list()
        for i, j, k  in zip(init_ratio, min_ratio, max_ratio):
            tk = transition_set(i, j, k)
            (samples, data, step_sizes) = self.generalized_chains(
                    param_min, param_max, tk, kernel, savefile,
                    initial_sample_type, criterion)
            results.append((samples, data))
            r_step_size.append(step_sizes)
            results_rD.append(int(sum(rho_D(data)/maximum)))
            mean_ss.append(np.mean(step_sizes))
        sort_ind = np.argsort(results_rD)
        return (results, r_step_size, results_rD, sort_ind, mean_ss)

    def run_inc_dec(self, increase, decrease, tolerance, rho_D, maximum,
            param_min, param_max, t_kernel, savefile,
            initial_sample_type="lhs", criterion='center'):
        """
        Generates samples using generalized chains and
        :class:`~bet.sampling.adaptiveSampling.rhoD_kernel` created using
        the `increase`, `decrease`, and `tolerance` parameters.

        :param list() increase: the multiple to increase the step size by
        :param list() decrease: the multiple to decrease the step size by
        :param list() tolerance: a tolerance used to determine if two
            different values are close
        :param rho_D: probability density on D
        :type rho_D: callable function that takes a :class:`np.array` and
            returns a :class:`numpy.ndarray`
        :param double maximum: maximum value of rho_D
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kernel: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
         :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :rtype: tuple
        :returns: ((samples, data), all_step_ratios, num_high_prob_samples,
            sorted_incidices_of_num_high_prob_samples, average_step_ratio)

        """
        kern_list = list()
        for i, j, z in zip(increase, decrease, tolerance):
            kern_list.append(rhoD_kernel(maximum, rho_D, i, j, z)) 
        return self.run_gen(kern_list, rho_D, maximum, param_min, param_max,
                t_kernel, savefile, initial_sample_type, criterion)

    def generalized_chains(self, param_min, param_max, t_kernel, kern,
            savefile, initial_sample_type="lhs", criterion='center'):
        """
        Basic adaptive sampling algorithm using generalized chains.
       
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kern: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :rtype: tuple
        :returns: (``parameter_samples``, ``data_samples``, ``all_step_ratios``) where
            ``parameter_samples`` is np.ndarray of shape (num_samples, ndim),
            ``data_samples`` is np.ndarray of shape (num_samples, mdim), and 
            ``all_step_ratios`` is np.ndarray of shape (num_chains,
            chain_length)

        """
        if size > 1:
            savefile = os.path.join(os.path.dirname(savefile),
                    "proc{}{}".format(rank, os.path.basename(savefile)))

        # Initialize Nx1 vector Step_size = something reasonable (based on size
        # of domain and transition set type)
        # Calculate domain size
        param_left = np.repeat([param_min], self.num_chains_pproc, 0)
        param_right = np.repeat([param_max], self.num_chains_pproc, 0)
        param_width = param_right - param_left
        # Calculate step_size
        max_ratio = t_kernel.max_ratio
        min_ratio = t_kernel.min_ratio
        step_ratio = t_kernel.init_ratio*np.ones(self.num_chains_pproc)
       
        # Initiative first batch of N samples (maybe taken from latin
        # hypercube/space-filling curve to fully explore parameter space - not
        # necessarily random). Call these Samples_old.
        (samples_old, data_old) = super(sampler, self).random_samples(
                initial_sample_type, param_min, param_max, savefile,
                self.num_chains, criterion)
        self.num_samples = self.chain_length * self.num_chains
        comm.Barrier()
        
        # now split it all up
        MYsamples_old = np.empty((np.shape(samples_old)[0]/size, np.shape(samples_old)[1]))
        comm.Scatter([samples_old, MPI.DOUBLE], [MYsamples_old, MPI.DOUBLE])
        MYdata_old = np.empty((np.shape(data_old)[0]/size, np.shape(data_old)[1]))
        comm.Scatter([data_old, MPI.DOUBLE], [MYdata_old,
            MPI.DOUBLE])

        samples = MYsamples_old
        data = MYdata_old
        all_step_ratios = step_ratio
        (kern_old, proposal) = kern.delta_step(MYdata_old, None)
        mdat = dict()
        self.update_mdict(mdat)

        for batch in xrange(1, self.chain_length):
            # For each of N samples_old, create N new parameter samples using
            # transition set and step_ratio. Call these samples samples_new.
            samples_new = t_kernel.step(step_ratio, param_width,
                    param_left, param_right, MYsamples_old)
            
            # Solve the model for the samples_new.
            data_new = self.lb_model(samples_new)
            
            # Make some decision about changing step_size(k).  There are
            # multiple ways to do this.
            # Determine step size
            (kern_old, proposal) = kern.delta_step(data_new, kern_old)
            step_ratio = proposal*step_ratio
            # Is the ratio greater than max?
            step_ratio[step_ratio > max_ratio] = max_ratio
            # Is the ratio less than min?
            step_ratio[step_ratio < min_ratio] = min_ratio

            # Save and export concatentated arrays
            if self.chain_length < 4:
                pass
            elif (batch+1)%(self.chain_length/4) == 0:
                print "Current chain length: "+str(batch+1)+"/"+str(self.chain_length)
            samples = np.concatenate((samples, samples_new))
            data = np.concatenate((data, data_new))
            all_step_ratios = np.concatenate((all_step_ratios, step_ratio))
            mdat['step_ratios'] = all_step_ratios
            mdat['samples'] = samples
            mdat['data'] = data
            super(sampler, self).save(mdat, "p"+str(rank)+savefile)

            # samples_old = samples_new
            MYsamples_old = samples_new

        # collect everything
        MYsamples = np.copy(samples)
        MYdata = np.copy(data)
        MYall_step_ratios = np.copy(all_step_ratios)
        # ``parameter_samples`` is np.ndarray of shape (num_samples, ndim)
        samples = np.empty((self.num_samples, np.shape(MYsamples)[1]), dtype=np.float64)
        # and ``data_samples`` is np.ndarray of shape (num_samples, mdim)
        data = np.empty((self.num_samples, np.shape(MYdata)[1]), dtype=np.float64)
        all_step_ratios = np.empty((self.num_chains, self.chain_length), dtype=np.float64)
        # now allgather
        comm.Allgather([MYsamples, MPI.DOUBLE], [samples, MPI.DOUBLE])
        comm.Allgather([MYdata, MPI.DOUBLE], [data, MPI.DOUBLE])
        comm.Allgather([MYall_step_ratios, MPI.DOUBLE], [all_step_ratios, MPI.DOUBLE])

        # save everything
        mdat['step_ratios'] = all_step_ratios
        mdat['samples'] = samples
        mdat['data'] = data
        super(sampler, self).save(mdat, savefile)

        return (samples, data, all_step_ratios)

    def reseed_chains(self, param_min, param_max, t_kernel, kern,
            savefile, initial_sample_type="lhs", criterion='center', reseed=1):
        """
        Basic adaptive sampling algorithm.

        NOT YET IMPLEMENTED.
       
        :param string initial_sample_type: type of initial sample random (or r),
            latin hypercube(lhs), or space-filling curve(TBD)
        :param param_min: minimum value for each parameter dimension
        :type param_min: np.array (ndim,)
        :param param_max: maximum value for each parameter dimension
        :type param_max: np.array (ndim,)
        :param t_kernel: method for creating new parameter steps using
            given a step size based on the paramter domain size
        :type t_kernel: :class:~`t_kernel`
        :param function kern: functional that acts on the data used to
            determine the proposed change to the ``step_size``
        :param string savefile: filename to save samples and data
        :param string criterion: latin hypercube criterion see 
            `PyDOE <http://pythonhosted.org/pyDOE/randomized.html>`_
        :param int reseed: number of times to reseed the chains
        :rtype: tuple
        :returns: (``parameter_samples``, ``data_samples``) where
            ``parameter_samples`` is np.ndarray of shape (num_samples, ndim)
            and ``data_samples`` is np.ndarray of shape (num_samples, mdim)

        """
        pass

def kernels(Q_ref, rho_D, maximum):
    """
    Generates a list of kernstic objects.

    :param Q_ref: reference parameter value
    :type Q_ref: :class:`np.ndarray`
    :param rho_D: probability density on D
    :type rho_D: callable function that takes a :class:`np.array` and returns
        a class:`np.ndarray`
    :param double maximum: maximum value of rho_D
    :rtype: list()
    :returns: [maxima_mean_kernel, rhoD_kernel, maxima_kernel,
        multi_dist_kernel]

    """
    kern_list = list()
    kern_list.append(maxima_mean_kernel(np.array([Q_ref]), rho_D))
    kern_list.append(rhoD_kernel(maximum, rho_D))
    kern_list.append(maxima_kernel(np.array([Q_ref]), rho_D))
    kern_list.append(multi_dist_kernel())
    return kern_list

class transition_set(object):
    """
    Basic class that is used to create a step to move from samples_old to
    samples_new based. This class generates steps for a random walk using a
    very basic algorithm. Future classes will inherit from this one with
    different implementations of the
    :meth:~`polysim.run_framework.apdative_sampling.step` method.

    This basic transition set is designed without a preferential direction.

    init_ratio
        Initial step size ratio compared to the parameter domain.
    min_ratio
        Minimum step size compared to the initial step size.
    max_ratio
        Maximum step size compared to the maximum step size.
    """

    def __init__(self, init_ratio, min_ratio, max_ratio):
        """
        Initialization
        """
        self.init_ratio = init_ratio
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
    
    def step(self, step_ratio, param_width, param_left, param_right,
            samples_old): 
        """
        Generate ``num_samples`` new steps using ``step_ratio`` and
        ``param_width`` to calculate the ``step size``. Each step will have a
        random direction.

        :param step_ratio: define maximum step_size = ``step_ratio*param_width``
        :type step_ratio: :class:`np.array` of shape (num_samples,)
        :param param_width: width of the parameter domain
        :type param_width: np.array (ndim,)
        :param samples_old: Parameter samples from the previous step.
        :type samples_old: :class:`~numpy.ndarray` of shape (num_samples,
            ndim)
        :rtype: :class:`np.array` of shape (num_samples, ndim)
        :returns: samples_new

        """
        # calculate maximum step size
        step_size = np.repeat([step_ratio], param_width.shape[1],
                0).transpose()*param_width
        # check to see if step will take you out of parameter space
        # calculate maximum proposed step
        samples_right = samples_old + 0.5*step_size
        samples_left = samples_old - 0.5*step_size
        # Is the new sample greaters than the right limit?
        far_right = samples_right >= param_right
        far_left = samples_left <= param_left
        # If the samples could leave the domain then truncate the box defining
        # the step_size
        samples_right[far_right] = param_right[far_right]
        samples_left[far_left] = param_left[far_left]
        samples_width = samples_right-samples_left
        #samples_center = (samples_right+samples_left)/2.0
        samples_new = samples_width * np.random.random(samples_old.shape)
        samples_new = samples_new + samples_left
        
        return samples_new

class kernel(object):
    """
    Parent class for kernels to determine change in step size. This class
    provides a method for determining the proposed change in step size. Since
    this is simply a skeleton parent class it does not change the step size at
    all.
    
    tolerance
        a tolerance used to determine if two different values are close
    increase
        the multiple to increase the step size by
    decrease
        the multiple to decrease the step size by
    """

    def __init__(self, tolerance=1E-08, increase=1.0, decrease=1.0):
        """
        Initialization
        """
        self.TOL = tolerance
        self.increase = increase
        self.decrease = decrease

    def delta_step(self, data_new, kern_old=None):
        """
        This method determines the proposed change in step size. 

        :param data_new: QoI for a given batch of samples 
        :type data_new: :class:`np.array` of shape (num_chains, mdim)
        :param kern_old: kernel evaluated at previous step
        :rtype: typle
        :returns: (kern_new, proposal)

        """
        return (None, np.ones((data_new.shape[0],)))

class rhoD_kernel(kernel):
    """
    We assume we know the distribution rho_D on the QoI and that the goal is to
    determine inverse regions of high probability accurately (in terms of
    getting the measure correct). This class provides a method for determining
    the proposed change in step size as follows. We check if the QoI at each of
    the samples_new(k) are closer or farther away from a region of high
    probability in D than the QoI at samples_old(k).  For example, if they are
    closer, then we can reduce the step_size(k) by 1/2.

    Note: This only works well with smooth rho_D.

    maximum
        maximum value of rho_D on D
    rho_D
        probability density on D
    tolerance 
        a tolerance used to determine if two different values are close
    increase
        the multiple to increase the step size by
    decrease
        the multiple to decrease the step size by

    """

    def __init__(self, maximum, rho_D, tolerance=1E-08, increase=2.0, 
            decrease=0.5):
        """
        Initialization
        """
        self.MAX = maximum
        self.rho_D = rho_D
        self.sort_ascending = False
        super(rhoD_kernel, self).__init__(tolerance, increase, decrease)

    def delta_step(self, data_new, kern_old=None):
        """
        This method determines the proposed change in step size. 
        
        :param data_new: QoI for a given batch of samples 
        :type data_new: :class:`np.array` of shape (num_chains, mdim)
        :param kern_old: kernel evaluated at previous step
        :rtype: tuple
        :returns: (kern_new, proposal)

        """
        # Evaluate kernel for new data.
        kern_new = self.rho_D(data_new)

        if kern_old == None:
            return (kern_new, None)
        else:
            kern_diff = (kern_new-kern_old)/self.MAX
            # Compare to kernel for old data.
            # Is the kernel NOT close?
            kern_close = np.logical_not(np.isclose(kern_diff, 0,
                atol=self.TOL))
            kern_max = np.isclose(kern_new, self.MAX, atol=self.TOL)
            # Is the kernel greater/lesser?
            kern_greater = np.logical_and(kern_diff > 0, kern_close)
            kern_greater = np.logical_or(kern_greater, kern_max)
            kern_lesser = np.logical_and(kern_diff < 0, kern_close)

            # Determine step size
            proposal = np.ones(kern_new.shape)
            proposal[kern_greater] = self.decrease
            proposal[kern_lesser] = self.increase
            return (kern_new, proposal.transpose())


class maxima_kernel(kernel):
    """
    We assume we know the maxima of the distribution rho_D on the QoI and that
    the goal is to determine inverse regions of high probability accurately (in
    terms of getting the measure correct). This class provides a method for
    determining the proposed change in step size as follows. We check if the
    QoI at each of the samples_new(k) are closer or farther away from a region
    of high probability in D than the QoI at samples_old(k). For example, if
    they are closer, then we can reduce the step_size(k) by 1/2.

    maxima
        locations of the maxima of rho_D on D
        np.array of shape (num_maxima, mdim)
    rho_max
        rho_D(maxima), list of maximum values of rho_D
    tolerance 
        a tolerance used to determine if two different values are close
    increase
        the multiple to increase the step size by
    decrease
        the multiple to decrease the step size by

    """

    def __init__(self, maxima, rho_D, tolerance=1E-08, increase=2.0, 
            decrease=0.5):
        """
        Initialization
        """
        self.MAXIMA = maxima
        self.num_maxima = maxima.shape[0]
        self.rho_max = rho_D(maxima)
        super(maxima_kernel, self).__init__(tolerance, increase, decrease)
        self.sort_ascending = True

    def delta_step(self, data_new, kern_old=None):
        """
        This method determines the proposed change in step size. 
        
        :param data_new: QoI for a given batch of samples 
        :type data_new: :class:`np.array` of shape (num_chains, mdim)
        :param kern_old: kernel evaluated at previous step
        :rtype: tuple
        :returns: (kern_new, proposal)

        """
        # Evaluate kernel for new data.
        kern_new = np.zeros((data_new.shape[0]))

        for i in xrange(data_new.shape[0]):
            # calculate distance from each of the maxima
            vec_from_maxima = np.repeat([data_new[i, :]], self.num_maxima, 0)
            vec_from_maxima = vec_from_maxima - self.MAXIMA
            # weight distances by 1/rho_D(maxima)
            dist_from_maxima = np.linalg.norm(vec_from_maxima, 2,
                1)/self.rho_max
            # set kern_new to be the minimum of weighted distances from maxima
            kern_new[i] = np.min(dist_from_maxima)

        if kern_old == None:
            return (kern_new, None)
        else:
            kern_diff = (kern_new-kern_old)
            # Compare to kernel for old data.
            # Is the kernel NOT close?
            kern_close = np.logical_not(np.isclose(kern_diff, 0,
                atol=self.TOL))
            # Is the kernel greater/lesser?
            kern_greater = np.logical_and(kern_diff > 0, kern_close)
            kern_lesser = np.logical_and(kern_diff < 0, kern_close)
            # Determine step size
            proposal = np.ones(kern_new.shape)
            # if further than kern_old then increase
            proposal[kern_greater] = self.increase
            # if closer than kern_old then decrease
            proposal[kern_lesser] = self.decrease
        return (kern_new, proposal)


class maxima_mean_kernel(maxima_kernel):
    """
    We assume we know the maxima of the distribution rho_D on the QoI and that
    the goal is to determine inverse regions of high probability accurately (in
    terms of getting the measure correct). This class provides a method for
    determining the proposed change in step size as follows. We check if the
    QoI at each of the samples_new(k) are closer or farther away from a region
    of high probability in D than the QoI at samples_old(k). For example, if
    they are closer, then we can reduce the step_size(k) by 1/2.

    maxima
        locations of the maxima of rho_D on D
        np.array of shape (num_maxima, mdim)
    rho_max
        rho_D(maxima), list of maximum values of rho_D
    tolerance 
        a tolerance used to determine if two different values are close
    increase
        the multiple to increase the step size by
    decrease
        the multiple to decrease the step size by

    """

    def __init__(self, maxima, rho_D, tolerance=1E-08, increase=2.0, 
            decrease=0.5):
        """
        Initialization
        """
        self.radius = None
        self.mean = None
        self.current_clength = 0
        super(maxima_mean_kernel, self).__init__(maxima, rho_D, tolerance,
                increase, decrease)

    def reset(self):
        """
        Resets the the batch number and the estimates of the mean and maximum
        distance from the mean.
        """
        self.radius = None
        self.mean = None
        self.current_clength = 0

    def delta_step(self, data_new, kern_old=None):
        """
        This method determines the proposed change in step size. 
        
        :param data_new: QoI for a given batch of samples 
        :type data_new: :class:`np.array` of shape (num_chains, mdim)
        :param kern_old: kernel evaluated at previous step
        :rtype: tuple
        :returns: (kern_new, proposal)

        """
        # Evaluate kernel for new data.
        kern_new = np.zeros((data_new.shape[0]))
        self.current_clength = self.current_clength + 1

        for i in xrange(data_new.shape[0]):
            # calculate distance from each of the maxima
            vec_from_maxima = np.repeat([data_new[i, :]], self.num_maxima, 0)
            vec_from_maxima = vec_from_maxima - self.MAXIMA
            # weight distances by 1/rho_D(maxima)
            dist_from_maxima = np.linalg.norm(vec_from_maxima, 2,
                1)/self.rho_max
            # set kern_new to be the minimum of weighted distances from maxima
            kern_new[i] = np.min(dist_from_maxima)

        if kern_old == None:
            # calculate the mean
            self.mean = np.mean(data_new, 0)
            # calculate the distance from the mean
            vec_from_mean = data_new - np.repeat([self.mean],
                    data_new.shape[0], 0)
            # estimate the radius of D
            self.radius = np.max(np.linalg.norm(vec_from_mean, 2, 1))
            return (kern_new, None)
        else:
            # update the estimate of the mean
            self.mean = (self.current_clength-1)*self.mean + np.mean(data_new,
                    0) 
            self.mean = self.mean / self.current_clength
            # calculate the distance from the mean
            vec_from_mean = data_new - np.repeat([self.mean],
                    data_new.shape[0], 0)
            # esitmate the radius of D
            self.radius = max(np.max(np.linalg.norm(vec_from_mean, 2, 1)),
                    self.radius)
            # calculate the relative change in distance
            kern_diff = (kern_new-kern_old)
            # normalize by the radius of D (IF POSSIBLE)
            kern_diff = kern_diff #/ self.radius
            # Compare to kernel for old data.
            # Is the kernel NOT close?
            kern_close = np.logical_not(np.isclose(kern_diff, 0,
                atol=self.TOL))
            # Is the kernel greater/lesser?
            kern_greater = np.logical_and(kern_diff > 0, kern_close)
            kern_lesser = np.logical_and(kern_diff < 0, kern_close)
            # Determine step size
            proposal = np.ones(kern_new.shape)
            # if further than kern_old then increase
            proposal[kern_greater] = self.increase
            # if closer than kern_old then decrease
            proposal[kern_lesser] = self.decrease
        return (kern_new, proposal)


class multi_dist_kernel(kernel):
    """
    The goal is to make a sampling that is robust to different types of
    distributions on QoI, i.e., we do not know a priori where the regions of
    high probability are in D. This class provides a method for determining the
    proposed step size as follows. We keep track of the change of the QoI
    values from one sample to the next compared to the total range of QoI
    values explored so far. If a big relative change is detected, then you know
    that you have come across a region with larger derivatives and you should
    place more samples around there to resolve the induced regions of
    generalized contours, i.e., reduce the step size. If the change in QoI
    values is relatively small, you are in a region where there is little
    sensitivity, so take larger step sizes.

    radius
        current estimate of the radius of D (1/2 the diameter of D)
    mean
        current estimate of the mean QoI
    current_clength
        current batch number
    TOL 
        a tolerance used to determine if two different values are close
    increase
        the multiple to increase the step size by
    decrease
        the multiple to decrease the step size by

    """

    def __init__(self, tolerance=1E-08, increase=2.0, 
            decrease=0.5):
        """
        Initialization
        """
        self.radius = None
        self.mean = None
        self.current_clength = 0
        super(multi_dist_kernel, self).__init__(tolerance, increase,
                decrease)

    def reset(self):
        """
        Resets the the batch number and the estimates of the mean and maximum
        distance from the mean.
        """
        self.radius = None
        self.mean = None
        self.current_clength = 0

    def delta_step(self, data_new, kern_old=None):
        """
        This method determines the proposed change in step size. 
        
        :param data_new: QoI for a given batch of samples 
        :type data_new: :class:`np.array` of shape (num_chains, mdim)
        :param kern_old: QoI evaluated at previous step
        :rtype: tuple
        :returns: (kern_new, proposal)

        """
        # Evaluate kernel for new data.
        kern_new = data_new
        self.current_clength = self.current_clength + 1

        if kern_old == None:
            proposal = None
            # calculate the mean
            self.mean = np.mean(data_new, 0)
            # calculate the distance from the mean
            vec_from_mean = kern_new - np.repeat([self.mean],
                    kern_new.shape[0], 0)
            # estimate the radius of D
            self.radius = np.max(np.linalg.norm(vec_from_mean, 2, 1)) 
        else:
            # update the estimate of the mean
            self.mean = (self.current_clength-1)*self.mean + np.mean(data_new, 0)
            self.mean = self.mean / self.current_clength
            # calculate the distance from the mean
            vec_from_mean = kern_new - np.repeat([self.mean],
                    kern_new.shape[0], 0)
            # esitmate the radius of D
            self.radius = max(np.max(np.linalg.norm(vec_from_mean, 2, 1)),
                    self.radius)
            # calculate the relative change in QoI
            kern_diff = (kern_new-kern_old)
            # normalize by the radius of D
            kern_diff = np.linalg.norm(vec_from_mean, 2, 1)#/self.radius
            # Compare to kernel for old data.
            # Is the kernel NOT close?
            kern_close = np.logical_not(np.isclose(kern_diff, 0,
                atol=self.TOL))
            # Is the kernel greater/lesser?
            kern_greater = np.logical_and(kern_diff > 0, kern_close)
            kern_lesser = np.logical_and(kern_diff < 0, kern_close)
            # Determine step size
            proposal = np.ones(kern_diff.shape)
            proposal[kern_greater] = self.decrease
            proposal[kern_lesser] = self.increase
        return (kern_new, proposal)




