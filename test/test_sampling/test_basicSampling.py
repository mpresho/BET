# Lindley Graham 04/07/2015
"""
This module contains unittests for :mod:`~bet.sampling.basicSampling:`
"""

import unittest, os
import numpy.testing as nptest
import numpy as np
import bet.sampling.basicSampling as bsam
import scipy.io as sio
import bet

local_path = os.path.join(os.path.dirname(bet.__file__), "../test/test_sampling")

def test_in_high_prob():
    """
    TODO :maybe move to test.test_postProcessing.test_postTools

    Tests :meth:`bet.sampling.basicSampling.in_high_prob`
    """
    def rho_D(my_data):
        return my_data/4.0
    data = np.array([0, 1, 0, 1, 1, 1])
    maximum = np.max(rho_D(data))
    print "maximum", maximum
    assert 4 == bsam.in_high_prob(data, rho_D, maximum)
    assert 3 == bsam.in_high_prob(data, rho_D, maximum, [3, 4, 5])
    assert 2 == bsam.in_high_prob(data, rho_D, maximum, [0, 1, 2, 3])
    assert 1 == bsam.in_high_prob(data, rho_D, maximum, [0, 2, 4])
    assert 0 == bsam.in_high_prob(data, rho_D, maximum, [0, 2])

def test_in_high_prob_multi():
    """
    TODO :maybe move to test.test_postProcessing.test_postTools

    Tests :meth:`bet.sampling.basicSampling.in_high_prob_multi`
    
    """
    def rho_D(my_data):
        return my_data/4.0
    data1 = np.array([0, 1, 0, 1, 1, 0])
    data2 = np.ones(data1.shape)-data1
    maximum = np.max(rho_D(data1))

    print "maximum", maximum
    results_list = [[None, data1], [None, data2], [None, data1], [None, data2]]
    sample_nos_list = [[3, 4, 5], [3, 4, 5], [0, 2, 4], [0, 2, 4]]

    nptest.assert_array_equal(np.array([2, 1, 1, 2]),
            bsam.in_high_prob_multi(results_list, rho_D, maximum,
                sample_nos_list))
    nptest.assert_array_equal(np.array([3, 3, 3, 3]),
            bsam.in_high_prob_multi(results_list, rho_D, maximum))

def test_loadmat():
    """
    Tests :meth:`bet.sampling.basicSampling.loadmat`
    """
    mdat1 = {'samples':np.random.random((5,1)),
            'data':np.random.random((5,1)), 'num_samples':5}
    mdat2 = {'samples':np.random.random((6,1)), 'num_samples':6}
    model = "this is not a model"

    sio.savemat('testfile1', mdat1)
    sio.savemat('testfile2', mdat2)

    (loaded_sampler1, samples1, data1) = bsam.loadmat('testfile1')
    nptest.assert_array_equal(samples1, mdat1['samples'])
    nptest.assert_array_equal(data1, mdat1['data'])
    assert loaded_sampler1.num_samples == 5
    assert loaded_sampler1.lb_model == None

    (loaded_sampler2, samples2, data2) = bsam.loadmat('testfile2', model)
    nptest.assert_array_equal(samples2, mdat2['samples'])
    nptest.assert_array_equal(data2, None)
    assert loaded_sampler2.num_samples == 6
    assert loaded_sampler2.lb_model == model
    if os.path.exists(os.path.join(local_path, 'testfile1.mat')):
        os.remove(os.path.join(local_path, 'testfile1.mat'))
    if os.path.exists(os.path.join(local_path, 'testfile2.mat')):
        os.remove(os.path.join(loca_path, 'testfile2.mat'))

def verify_user_samples(model, sampler, samples, savefile, parallel):
    # evalulate the model at the samples directly
    data = model(samples)

    # evaluate the model at the samples
    (my_samples, my_data) = sampler.user_samples(samples, savefile,
            parallel)

    if len(data.shape) == 1:
        data = np.expand_dims(data, axis=1)
    if len(samples.shape) == 1:
        samples = np.expan_dims(samples, axis=1)
    
    # compare the samples
    nptest.assert_array_equal(samples, my_samples)
    # compare the data
    nptest.assert_array_equal(data, my_data)
    # did num_samples get updated?
    assert samples.shape[0] == sampler.num_samples
    # did the file get correctly saved?

    mdat = sio.loadmat('savefile')
    nptest.assert_array_equal(samples, mdat['samples'])
    nptest.assert_array_equal(data, mdat['data'])
    assert samples.shape[0] == sampler.num_samples

def verify_random_samples(model, sampler, sample_type, param_min, param_max,
        num_samples, savefile, parallel):
    # recreate the samples
    if num_samples == None:
        num_samples = self.num_samples
    param_left = np.repeat([param_min], num_samples, 0)
    param_right = np.repeat([param_max], num_samples, 0)
    samples = (param_right-param_left)
    if sample_type == "lhs":
        samples = samples * lhs(param_min.shape[-1], num_samples, criterion)
    elif sample_type == "random" or "r":
        np.random.seed(1)
        samples = samples * np.random(param_left.shape)
    samples = samples + param_left
    # evalulate the model at the samples directly
    data = model(samples)

    # evaluate the model at the samples
    # reset the random seed
    if sample_type == "random" or "r":
        np.random.seed(1)
    (my_samples, my_data) = sampler.user_samples(samples, savefile,
            parallel)

    # make sure that the samples are within the boundaries
    assert np.all(my_samples <= param_right)
    assert np.all(my_samples >= param_left)

    if len(data.shape) == 1:
        data = np.expand_dims(data, axis=1)
    if len(samples.shape) == 1:
        samples = np.expan_dims(samples, axis=1)
    
    # compare the samples
    nptest.assert_array_equal(samples, my_samples)
    # compare the data
    nptest.assert_array_equal(data, my_data)
    # did num_samples get updated?
    assert samples.shape[0] == sampler.num_samples
    # did the file get correctly saved?

    mdat = sio.loadmat('savefile')
    nptest.assert_array_equal(samples, mdat['samples'])
    nptest.assert_array_equal(data, mdat['data'])
    assert samples.shape[0] == sampler.num_samples


class Test_basic_sampler(unittest.TestCase):
    """
    Test :class:`bet.sampling.basicSampling.sampler`.
    """

    def setUp(self):
        # create 1-1 map
        self.param_min1 = np.zeros((1, ))
        self.param_max1 = np.zeros((1, ))
        def map_1t1(x):
            return np.sin(x)
        # create 3-1 map
        self.param_min3 = np.zeros((3, ))
        self.param_max3 = np.ones((3, ))
        def map_3t1(x):
            return np.sum(x, 1)
        # create 3-2 map
        def map_3t2(x):
            return np.vstack(([x[:, 0]+x[:, 1], x[:, 2]])).transpose()
        # create 10-4 map
        self.param_min10 = np.zeros((10, ))
        self.param_min10 = np.ones((10, ))
        def map_10t4(x):
            x1 = x[:, 0] + x[:, 1]
            x2 = x[:, 2] + x[:, 3]
            x3 = x[:, 4] + x[:, 5]
            x4 = np.sum(x[:, [6, 7, 8, 9]], 1)
            return np.vstack([x1, x2, x3, x4]).transpose()
        num_samples = 100
        self.savefiles = ["11t11", "1t1", "3to1", "3to2", "10to4"]
        self.models = [map_1t1, map_1t1, map_3t1, map_3t2, map_10t4]
        self.samplers = []
        for model in self.models:
            self.samplers.append(bsam.sampler(model, num_samples))

    def tearDown(self):
        for f in self.savefiles:
            if os.path.exists(os.path.join(local_path, f, ".mat")):
                os.remove(os.path.join(local_path, f, ".mat"))

    def test_init(self):
        """
        Test initalization of :class:`bet.sampling.basicSampling.sampler`
        """
        assert self.samplers[0].num_samples == 100
        assert self.samplers[0].lb_model == self.models[0]
        assert bsam.sampler(self.models[0], None).num_samples == None

    @unittest.skip("Skipping testing saving")
    def test_save(self):
        pass

    def test_update(self):
        """
        Test :meth:`bet.sampling.basicSampling.sampler.save`
        """
        mdict = {"frog":3, "moose":2}
        self.samplers[0].update_mdict(mdict)
        assert self.samplers[0].num_samples == mdict["num_samples"]

    def test_user_samples(self):
        """
        Test :meth:`bet.sampling.basicSampling.sampler.random_samples` for
        three different QoI maps (1 to 1, 3 to 1, 3 to 2, 10 to 4).
        """
        # create a list of different sets of samples
        list_of_samples = [np.ones((4, )), np.ones((4, 1)), np.ones((4, 3)),
                np.ones((4, 3)), np.ones((4, 10))]
        
        test_list = zip(self.models, self.samplers, list_of_samples, 
                self.savefiles)
        
        for model, sampler, samples, savefile in test_list: 
            for parallel in [False, True]:
                yield verify_user_samples, model, sampler, samples, savefile, parallel

    def test_random_samples(self):
        """
        Test :met:`bet.sampling.basicSampling.sampler.random_samples` for three
        different QoI maps (1 to 1, 3 to 1, 3 to 2, 10 to 4).
        """
        param_min_list = [self.param_min1, self.param_min1, self.param_min3,
            self.param_min3, self.param_min10]
        param_max_list = [self.param_max1, self.param_max1, self.param_max3,
            self.param_max3, self.param_max10]

        test_list = zip(self.models, self.samplers, param_min_list,
                param_max_list,
                self.savefiles)

        for model, sampler, param_min, param_max, savefile in test_list:
            for sample_type in ["random", "r", "lhs"]:
                for num_samples in [None, 25]:
                    for parallel in [False, True]:
                        yield verify_random_samples, model, sampler,
                        param_min, param_max, savefile, num_samples,
                        parallel
