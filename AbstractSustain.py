###
# pySuStaIn: Python translation of Matlab version of SuStaIn algorithm (https://www.nature.com/articles/s41467-018-05892-0)
# Author: Peter Wijeratne (p.wijeratne@ucl.ac.uk)
# Contributors: Leon Aksman (l.aksman@ucl.ac.uk), Arman Eshaghi (a.eshaghi@ucl.ac.uk)
#
# For questions/comments related to:
# Leon's Object Oriented pySustain (LOOpySustain) implementation of AbstractSustain, ZscoreSustain, MixtureSustain classes
# contact: Leon Aksman (l.aksman@ucl.ac.uk)
###
from abc import ABC, abstractmethod

import numpy as np
from matplotlib import pyplot as plt
from pathlib import Path
import pickle
import csv
import os

#*******************************************
#The data structure class for AbstractSustain. It has no data itself - the implementations of AbstractSustain need to define their own implementations of this class.
class AbstractSustainData(ABC):

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def getNumSamples(self):
        pass

    @abstractmethod
    def getNumBiomarkers(self):
        pass

    @abstractmethod
    def getNumStages(self):
        pass

    @abstractmethod
    def reindex(self, index):
        pass

#*******************************************
class AbstractSustain(ABC):


    def __init__(self,
                 sustainData,
                 N_startpoints,
                 N_S_max,
                 N_iterations_MCMC,
                 output_folder,
                 dataset_name):

        assert(isinstance(sustainData, AbstractSustainData))

        self.__sustainData              = sustainData

        self.N_startpoints              = N_startpoints
        self.N_S_max                    = N_S_max
        self.N_iterations_MCMC          = N_iterations_MCMC

        self.output_folder              = output_folder
        self.dataset_name               = dataset_name

    #********************* PUBLIC METHODS
    def run_sustain_algorithm(self):

        ml_sequence_prev_EM                 = []
        ml_f_prev_EM                        = []


        fig0, ax0                           = plt.subplots()
        for s in range(self.N_S_max):

            pickle_filename_s               = self.output_folder + '/' + self.dataset_name + '_subtype' + str(s) + '.pickle'
            pickle_filepath                 = Path(pickle_filename_s)
            if pickle_filepath.exists():
                print("Found pickle file: " + pickle_filename_s + ". Using pickled variables for " + str(s) + " subtype.")

                pickle_file                 = open(pickle_filename_s, 'rb')

                loaded_variables            = pickle.load(pickle_file)

                #self.stage_zscore           = loaded_variables["stage_zscore"]
                #self.stage_biomarker_index  = loaded_variables["stage_biomarker_index"]
                #self.N_S_max                = loaded_variables["N_S_max"]

                samples_likelihood          = loaded_variables["samples_likelihood"]
                samples_sequence            = loaded_variables["samples_sequence"]
                samples_f                   = loaded_variables["samples_f"]

                ml_sequence_EM              = loaded_variables["ml_sequence_EM"]
                ml_sequence_prev_EM         = loaded_variables["ml_sequence_prev_EM"]
                ml_f_EM                     = loaded_variables["ml_f_EM"]
                ml_f_prev_EM                = loaded_variables["ml_f_prev_EM"]

                pickle_file.close()
            else:
                print("Failed to find pickle file: " + pickle_filename_s + ". Running SuStaIn model for " + str(s) + " subtype.")

                ml_sequence_EM,     \
                ml_f_EM,            \
                ml_likelihood_EM,   \
                ml_sequence_mat_EM, \
                ml_f_mat_EM,        \
                ml_likelihood_mat_EM        = self._estimate_ml_sustain_model_nplus1_clusters(self.__sustainData, ml_sequence_prev_EM, ml_f_prev_EM) #self.__estimate_ml_sustain_model_nplus1_clusters(self.__data, ml_sequence_prev_EM, ml_f_prev_EM)

                seq_init                    = ml_sequence_EM
                f_init                      = ml_f_EM

                ml_sequence,        \
                ml_f,               \
                ml_likelihood,      \
                samples_sequence,   \
                samples_f,          \
                samples_likelihood          = self._estimate_uncertainty_sustain_model(self.__sustainData, seq_init, f_init)           #self.__estimate_uncertainty_sustain_model(self.__data, seq_init, f_init)
                ml_sequence_prev_EM         = ml_sequence_EM
                ml_f_prev_EM                = ml_f_EM

            # max like subtype and stage / subject
            N_samples                       = 1000
            ml_subtype,             \
            prob_ml_subtype,        \
            ml_stage,               \
            prob_ml_stage                   = self.subtype_and_stage_individuals(self.__sustainData, samples_sequence, samples_f, N_samples)   #self.subtype_and_stage_individuals(self.__data, samples_sequence, samples_f, N_samples)
            if not pickle_filepath.exists():

                if not os.path.exists(self.output_folder):
                    os.makedirs(self.output_folder)

                save_variables                          = {}
                save_variables["samples_sequence"]      = samples_sequence
                save_variables["samples_f"]             = samples_f
                save_variables["samples_likelihood"]    = samples_likelihood

                save_variables["ml_subtype"]            = ml_subtype
                save_variables["prob_ml_subtype"]       = prob_ml_subtype
                save_variables["ml_stage"]              = ml_stage
                save_variables["prob_ml_stage"]         = prob_ml_stage

                save_variables["ml_sequence_EM"]        = ml_sequence_EM
                save_variables["ml_sequence_prev_EM"]   = ml_sequence_prev_EM
                save_variables["ml_f_EM"]               = ml_f_EM
                save_variables["ml_f_prev_EM"]          = ml_f_prev_EM

                pickle_file                 = open(pickle_filename_s, 'wb')
                pickle_output               = pickle.dump(save_variables, pickle_file)
                pickle_file.close()

            n_samples                       = self.__sustainData.getNumSamples() #self.__data.shape[0]

            # plot results
            fig, ax                         = self._plot_sustain_model(samples_sequence, samples_f, s, samples_likelihood, n_samples)
            fig.savefig(self.output_folder + '/' + self.dataset_name + '_subtype' + str(s) + '_PVD.png')
            fig.show()

            ax0.plot(range(self.N_iterations_MCMC), samples_likelihood, label="subtypes" + str(s))


        # save and show this figure after all subtypes have been calculcated
        ax0.legend(loc='upper right')
        fig0.savefig(self.output_folder + '/MCMC_likelihood' + str(self.N_iterations_MCMC) + '.png', bbox_inches='tight')
        fig0.show()

        return samples_sequence, samples_f, ml_subtype, prob_ml_subtype, ml_stage, prob_ml_stage

    def cross_validate_sustain_model(self, test_idxs, select_fold = []):

        # Cross-validate the SuStaIn model by running the SuStaIn algorithm (E-M
        # and MCMC) on a training dataset and evaluating the model likelihood on a test
        # dataset. 'data_fold' should specify the membership of each data point to a
        # test fold. Use a specific index of variable 'select_fold' to just run for a
        # single fold (allows the cross-validation to be run in parallel), or leave
        # the variable 'select_fold' empty to iterate across folds sequentially.

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        if select_fold:
            test_idxs                       = test_idxs[select_fold]
        Nfolds                              = len(test_idxs)

        for fold in range(Nfolds):


            #        print('Cross-validating fold',fold,'of',Nfolds,'with index',test_idxs[fold])
            indx_train                      = np.array([x for x in range(self.__sustainData.getNumSamples()) if x not in test_idxs[fold]])
            indx_test                       = test_idxs[fold]
            sustainData_train               = self.__sustainData.reindex(indx_train)
            sustainData_test                = self.__sustainData.reindex(indx_test)

            ml_sequence_prev_EM             = []
            ml_f_prev_EM                    = []
            #samples_sequence_cval           = []
            #samples_f_cval                  = []
            for s in range(self.N_S_max):


                pickle_filename_fold_s      = self.output_folder + '/' + self.dataset_name + '_fold' + str(fold) + '_subtype' + str(s) + '.pickle'
                pickle_filepath             = Path(pickle_filename_fold_s)

                if pickle_filepath.exists():

                    pickle_file             = open(pickle_filename_fold_s, 'rb')

                    loaded_variables        = pickle.load(pickle_file)

                    ml_sequence_EM          = loaded_variables["ml_sequence_EM"]
                    ml_sequence_prev_EM     = loaded_variables["ml_sequence_prev_EM"]
                    ml_f_EM                 = loaded_variables["ml_f_EM"]
                    ml_f_prev_EM            = loaded_variables["ml_f_prev_EM"]

                    samples_likelihood      = loaded_variables["samples_likelihood"]
                    samples_sequence        = loaded_variables["samples_sequence"]
                    samples_f               = loaded_variables["samples_f"]

                    samples_likelihood_subj_test = loaded_variables["samples_likelihood_subj_test"]

                    pickle_file.close()

                else:
                    ml_sequence_EM,         \
                    ml_f_EM,                \
                    ml_likelihood_EM,       \
                    ml_sequence_mat_EM,     \
                    ml_f_mat_EM,            \
                    ml_likelihood_mat_EM    = self._estimate_ml_sustain_model_nplus1_clusters(sustainData_train, ml_sequence_prev_EM, ml_f_prev_EM)


                    seq_init                    = ml_sequence_EM
                    f_init                      = ml_f_EM

                    ml_sequence,            \
                    ml_f,                   \
                    ml_likelihood,          \
                    samples_sequence,       \
                    samples_f,              \
                    samples_likelihood           = self._estimate_uncertainty_sustain_model(sustainData_test, seq_init, f_init)

                    samples_likelihood_subj_test = self._evaluate_likelihood_setofsamples(sustainData_test, samples_sequence, samples_f)

                    ml_sequence_prev_EM         = ml_sequence_EM
                    ml_f_prev_EM                = ml_f_EM

                    #samples_sequence_cval       += list(samples_sequence)
                    #samples_f_cval              += list(samples_f)

                    if not os.path.exists(self.output_folder):
                        os.makedirs(self.output_folder)

                    save_variables                                      = {}
                    save_variables["ml_sequence_EM"]                    = ml_sequence_EM
                    save_variables["ml_sequence_prev_EM"]               = ml_sequence_prev_EM
                    save_variables["ml_f_EM"]                           = ml_f_EM
                    save_variables["ml_f_prev_EM"]                      = ml_f_prev_EM

                    save_variables                                      = {}
                    save_variables["samples_sequence"]                  = samples_sequence
                    save_variables["samples_f"]                         = samples_f
                    save_variables["samples_likelihood"]                = samples_likelihood

                    save_variables["samples_likelihood_subj_test"]      = samples_likelihood_subj_test

                    pickle_file                 = open(pickle_filename_fold_s, 'wb')
                    pickle_output               = pickle.dump(save_variables, pickle_file)
                    pickle_file.close()

        """
        ###
        # UNDER CONSTRUCTION
        ###
        samples_sequence_cval = np.array(samples_sequence_cval)
        samples_f_cval = np.array(samples_f_cval)
        biomarker_labels = np.array([str(x) for x in range(data.shape[1])])
        fig, ax = plot_sustain_model(samples_sequence_cval,
                                     samples_f_cval,
                                     biomarker_labels,
                                     stage_zscore,
                                     stage_biomarker_index,
                                     N_S_max,
                                     output_folder,
                                     dataset_name,
                                     s,
                                     samples_likelihood,
                                     cval=True)
        """

    def subtype_and_stage_individuals(self, sustainData, samples_sequence, samples_f, N_samples):

        nSamples                            = sustainData.getNumSamples()  #data_local.shape[0]
        nStages                             = sustainData.getNumStages()    #self.stage_zscore.shape[1]

        n_iterations_MCMC                   = samples_sequence.shape[2]
        select_samples                      = np.round(np.linspace(0, n_iterations_MCMC - 1, N_samples))
        N_S                                 = samples_sequence.shape[0]
        temp_mean_f                         = np.mean(samples_f, axis=1)
        ix                                  = np.argsort(temp_mean_f)[::-1]

        prob_subtype_stage                  = np.zeros((nSamples, nStages + 1, N_S))
        prob_subtype                        = np.zeros((nSamples, N_S))
        prob_stage                          = np.zeros((nSamples, nStages + 1))

        for i in range(N_samples):
            sample                          = int(select_samples[i])

            this_S                          = samples_sequence[ix, :, sample]
            this_f                          = samples_f[ix, sample]

            _,                  \
            _,                  \
            total_prob_stage,   \
            total_prob_subtype, \
            total_prob_subtype_stage        = self._calculate_likelihood(sustainData, this_S, this_f)

            total_prob_subtype              = total_prob_subtype.reshape(len(total_prob_subtype), N_S)
            total_prob_subtype_norm         = total_prob_subtype        / np.tile(np.sum(total_prob_subtype, 1).reshape(len(total_prob_subtype), 1),        (1, N_S))
            total_prob_stage_norm           = total_prob_stage          / np.tile(np.sum(total_prob_stage, 1).reshape(len(total_prob_subtype), 1),          (1, nStages + 1))
            total_prob_subtype_stage_norm   = total_prob_subtype_stage  / np.tile(np.sum(np.sum(total_prob_subtype_stage, 1), 1).reshape(nSamples, 1, 1),   (1, nStages + 1, N_S))

            prob_subtype_stage              = (i / (i + 1.) * prob_subtype_stage)   + (1. / (i + 1.) * total_prob_subtype_stage_norm)
            prob_subtype                    = (i / (i + 1.) * prob_subtype)         + (1. / (i + 1.) * total_prob_subtype_norm)
            prob_stage                      = (i / (i + 1.) * prob_stage)           + (1. / (i + 1.) * total_prob_stage_norm)

        ml_subtype                          = np.nan * np.ones((nSamples, 1))
        prob_ml_subtype                     = np.nan * np.ones((nSamples, 1))
        ml_stage                            = np.nan * np.ones((nSamples, 1))
        prob_ml_stage                       = np.nan * np.ones((nSamples, 1))

        for i in range(nSamples):
            this_prob_subtype               = np.squeeze(prob_subtype[i, :])

            if (np.sum(np.isnan(this_prob_subtype)) == 0):
                this_subtype                = np.where(this_prob_subtype == np.max(this_prob_subtype))

                try:
                    ml_subtype[i]           = this_subtype
                except:
                    ml_subtype[i]           = this_subtype[0][0]
                if this_prob_subtype.size == 1 and this_prob_subtype == 1:
                    prob_ml_subtype[i]      = 1
                else:
                    try:
                        prob_ml_subtype[i]  = this_prob_subtype[this_subtype]
                    except:
                        prob_ml_subtype[i]  = this_prob_subtype[this_subtype[0][0]]

            this_prob_stage                 = np.squeeze(prob_subtype_stage[i, :, int(ml_subtype[i])])
            if (np.sum(np.isnan(this_prob_stage)) == 0):
                this_stage                  = np.where(this_prob_stage == np.max(this_prob_stage))
                ml_stage[i]                 = this_stage[0][0]
                prob_ml_stage[i]            = this_prob_stage[this_stage[0][0]]

        return ml_subtype, prob_ml_subtype, ml_stage, prob_ml_stage

    # ********************* PROTECTED METHODS
    def _estimate_ml_sustain_model_nplus1_clusters(self, sustainData, ml_sequence_prev, ml_f_prev):
        # Given the previous SuStaIn model, estimate the next model in the
        # hierarchy (i.e. number of subtypes goes from N to N+1)
        #
        #
        # OUTPUTS:
        # ml_sequence - the ordering of the stages for each subtype for the next
        # SuStaIn model in the hierarchy
        # ml_f - the most probable proportion of individuals belonging to each
        # subtype for the next SuStaIn model in the hierarchy
        # ml_likelihood - the likelihood of the most probable SuStaIn model for the
        # next SuStaIn model in the hierarchy
        # previous outputs _mat - same as before but for each start point

        N_S = len(ml_sequence_prev) + 1
        if N_S == 1:
            # If the number of subtypes is 1, fit a single linear z-score model
            print('Finding ML solution to 1 cluster problem')
            ml_sequence,        \
            ml_f,               \
            ml_likelihood,      \
            ml_sequence_mat,    \
            ml_f_mat,           \
            ml_likelihood_mat               = self._find_ml(sustainData)
            print('Overall ML likelihood is', ml_likelihood)

        else:
            # If the number of subtypes is greater than 1, go through each subtype
            # in turn and try splitting into two subtypes
            _, _, _, p_sequence, _          = self._calculate_likelihood(sustainData, ml_sequence_prev, ml_f_prev)

            ml_sequence_prev                = ml_sequence_prev.reshape(ml_sequence_prev.shape[0], ml_sequence_prev.shape[1])
            p_sequence                      = p_sequence.reshape(p_sequence.shape[0], N_S - 1)
            p_sequence_norm                 = p_sequence / np.tile(np.sum(p_sequence, 1).reshape(len(p_sequence), 1), (N_S - 1))

            # Assign individuals to a subtype (cluster) based on the previous model
            ml_cluster_subj                 = np.zeros((sustainData.getNumSamples(), 1))   #np.zeros((len(data_local), 1))
            for m in range(sustainData.getNumSamples()):                                   #range(len(data_local)):
                ix                          = np.argmax(p_sequence_norm[m, :]) + 1

                #TEMP: MATLAB comparison
                #ml_cluster_subj[m]          = ix*np.ceil(np.random.rand())
                ml_cluster_subj[m]          = ix  # FIXME: should check this always works, as it differs to the Matlab code, which treats ix as an array

            ml_likelihood                   = -np.inf
            for ix_cluster_split in range(N_S - 1):
                this_N_cluster              = sum(ml_cluster_subj == int(ix_cluster_split + 1))

                if this_N_cluster > 1:

                    # Take the data from the individuals belonging to a particular
                    # cluster and fit a two subtype model
                    print('Splitting cluster', ix_cluster_split + 1, 'of', N_S - 1)
                    #data_split              = data_local[(ml_cluster_subj == int(ix_cluster_split + 1)).reshape(len(data_local), )]
                    ix_i                    = (ml_cluster_subj == int(ix_cluster_split + 1)).reshape(sustainData.getNumSamples(), )
                    sustainData_i           = sustainData.reindex(ix_i)

                    print(' + Resolving 2 cluster problem')
                    this_ml_sequence_split, _, _, _, _, _ = self._find_ml_mixture2(sustainData_i)

                    # Use the two subtype model combined with the other subtypes to
                    # inititialise the fitting of the next SuStaIn model in the
                    # hierarchy
                    this_seq_init           = ml_sequence_prev.copy()  # have to copy or changes will be passed to ml_sequence_prev

                    this_seq_init[ix_cluster_split] = (this_ml_sequence_split[0]).reshape(this_ml_sequence_split.shape[1])

                    this_seq_init           = np.hstack((this_seq_init.T, this_ml_sequence_split[1])).T
                    this_f_init             = np.array([1.] * N_S) / float(N_S)

                    print(' + Finding ML solution from hierarchical initialisation')
                    this_ml_sequence,       \
                    this_ml_f,              \
                    this_ml_likelihood,     \
                    this_ml_sequence_mat,   \
                    this_ml_f_mat,          \
                    this_ml_likelihood_mat  = self._find_ml_mixture(sustainData, this_seq_init, this_f_init)

                    # Choose the most probable SuStaIn model from the different
                    # possible SuStaIn models initialised by splitting each subtype
                    # in turn
                    # FIXME: these arrays have an unnecessary additional axis with size = N_startpoints - remove it further upstream
                    if this_ml_likelihood[0] > ml_likelihood:
                        ml_likelihood       = this_ml_likelihood[0]
                        ml_sequence         = this_ml_sequence[:, :, 0]
                        ml_f                = this_ml_f[:, 0]
                        ml_likelihood_mat   = this_ml_likelihood_mat[0]
                        ml_sequence_mat     = this_ml_sequence_mat[:, :, 0]
                        ml_f_mat            = this_ml_f_mat[:, 0]
                    print('- ML likelihood is', this_ml_likelihood[0])
                else:
                    print('Cluster', ix_cluster_split + 1, 'of', N_S - 1, 'too small for subdivision')
            print('Overall ML likelihood is', ml_likelihood)

        return ml_sequence, ml_f, ml_likelihood, ml_sequence_mat, ml_f_mat, ml_likelihood_mat

    def _find_ml(self, sustainData):
        # Fit a linear z-score model
        #
        # OUTPUTS:
        # ml_sequence - the ordering of the stages for each subtype
        # ml_f - the most probable proportion of individuals belonging to each
        # subtype
        # ml_likelihood - the likelihood of the most probable SuStaIn model
        # previous outputs _mat - same as before but for each start point

        terminate                           = 0
        startpoint                          = 0

        ml_sequence_mat                     = np.zeros((1, sustainData.getNumStages(), self.N_startpoints)) #np.zeros((1, self.stage_zscore.shape[1], self.N_startpoints))
        ml_f_mat                            = np.zeros((1, self.N_startpoints))
        ml_likelihood_mat                   = np.zeros(self.N_startpoints)

        while terminate == 0:
            print(' ++ startpoint', startpoint)
            # randomly initialise the sequence of the linear z-score model
            seq_init                        = self._initialise_sequence(sustainData)  #self.__initialise_sequence_linearzscoremodel()
            f_init                          = [1]

            this_ml_sequence,   \
            this_ml_f,          \
            this_ml_likelihood, \
            _,                  \
            _,                  \
            _                               = self._perform_em(sustainData, seq_init, f_init)    #self.__perform_em_mixturelinearzscoremodels(data_local, seq_init, f_init)

            ml_sequence_mat[:, :, startpoint] = this_ml_sequence
            ml_f_mat[:, startpoint]         = this_ml_f
            ml_likelihood_mat[startpoint]   = this_ml_likelihood

            if startpoint == (self.N_startpoints - 1):
                terminate                   = 1
            startpoint                      += 1

        ix                                  = np.argmax(ml_likelihood_mat)
        ml_sequence                         = ml_sequence_mat[:, :, ix]
        ml_f                                = ml_f_mat[:, ix]
        ml_likelihood                       = ml_likelihood_mat[ix]

        return ml_sequence, ml_f, ml_likelihood, ml_sequence_mat, ml_f_mat, ml_likelihood_mat

    def _find_ml_mixture2(self, sustainData):

        # Fit a mixture of two linear z-score models
        #
        #
        # OUTPUTS:
        # ml_sequence - the ordering of the stages for each subtype
        # ml_f - the most probable proportion of individuals belonging to each
        # subtype
        # ml_likelihood - the likelihood of the most probable SuStaIn model
        # previous outputs _mat - same as before but for each start point
        N_S                                 = 2

        terminate                           = 0
        startpoint                          = 0

        ml_sequence_mat                     = np.zeros((N_S, sustainData.getNumStages(), self.N_startpoints))   #np.zeros((N_S, self.stage_zscore.shape[1], self.N_startpoints))
        ml_f_mat                            = np.zeros((N_S, self.N_startpoints))
        ml_likelihood_mat                   = np.zeros((self.N_startpoints, 1))

        while terminate == 0:
            print(' ++ startpoint', startpoint)

            # randomly initialise individuals as belonging to one of the two subtypes (clusters)
            min_N_cluster                   = 0
            while min_N_cluster == 0:
                #cluster_assignment          = np.array([np.ceil(x) for x in N_S * np.random.rand(data_local.shape[0])]).astype(int)
                cluster_assignment          = np.array([np.ceil(x) for x in N_S * np.random.rand(sustainData.getNumSamples())]).astype(int)

                temp_N_cluster              = np.zeros(N_S)
                for s in range(1, N_S + 1):
                    temp_N_cluster          = np.sum((cluster_assignment == s).astype(int), 0)  # FIXME? this means the last index always defines the sum...
                min_N_cluster               = min([temp_N_cluster])

            # initialise the stages of the two linear z-score models by fitting a
            # single linear z-score model to each of the two sets of individuals
            seq_init                        = np.zeros((N_S, sustainData.getNumStages()))
            for s in range(N_S):

                #temp_data                   = data_local[cluster_assignment.reshape(cluster_assignment.shape[0], ) == (s + 1), :]
                index_s                     = cluster_assignment.reshape(cluster_assignment.shape[0], ) == (s + 1)
                temp_sustainData            = sustainData.reindex(index_s)

                temp_seq_init               = self._initialise_sequence(sustainData)
                seq_init[s, :], _, _, _, _, _ = self._perform_em(temp_sustainData, temp_seq_init, [1])

            f_init                          = np.array([1.] * N_S) / float(N_S)

            # optimise the mixture of two linear z-score models from the
            # initialisation
            this_ml_sequence,   \
            this_ml_f,          \
            this_ml_likelihood, _, _, _     = self._perform_em(sustainData, seq_init, f_init)

            ml_sequence_mat[:, :, startpoint] = this_ml_sequence
            ml_f_mat[:, startpoint]         = this_ml_f
            ml_likelihood_mat[startpoint]   = this_ml_likelihood

            if startpoint == (self.N_startpoints - 1):
                terminate                   = 1

            startpoint                      += 1

        ix                                  = [np.where(ml_likelihood_mat == max(ml_likelihood_mat))[0][0]] #ugly bit of code to get first index where likelihood is maximum

        #if len(ix) > 1: # == self.N_startpoints:       #if len(ix) > 0:
        #    print("WARNING: perform_em_mixturelinearzscoremodels() within find_ml_mixture2linearzscoremodels() found same likelihood for all startpoints. Taking first one as best. Beware!")
        #    ix                              = [0]
        #else:
        #    ix                              = ix[0]

        ml_sequence                         = ml_sequence_mat[:, :, ix] #.squeeze()
        ml_f                                = ml_f_mat[:, ix]           #.squeeze()
        ml_likelihood                       = ml_likelihood_mat[ix]     #.squeeze()

        return ml_sequence, ml_f, ml_likelihood, ml_sequence_mat, ml_f_mat, ml_likelihood_mat

    def _find_ml_mixture(self, sustainData, seq_init, f_init):
        # Fit a mixture of linear z-score models
        #
        # INPUTS:
        # data - !important! needs to be (positive) z-scores!
        #   dim: number of subjects x number of biomarkers
        # min_biomarker_zscore - a minimum z-score for each biomarker (usually zero
        # for all markers)
        #   dim: 1 x number of biomarkers
        # max_biomarker_zscore - a maximum z-score for each biomarker - reached at
        # the final stage of the linear z-score model
        #   dim: 1 x number of biomarkers
        # std_biomarker_zscore - the standard devation of each biomarker z-score
        # (should be 1 for all markers)
        #   dim: 1 x number of biomarkers
        # stage_zscore and stage_biomarker_index give the different z-score stages
        # for the linear z-score model, i.e. the index of the different z-scores
        # for each biomarker
        # stage_zscore - the different z-scores of the model
        #   dim: 1 x number of z-score stages
        # stage_biomarker_index - the index of the biomarker that the corresponding
        # entry of stage_zscore is referring to - !important! ensure biomarkers are
        # indexed s.t. they correspond to columns 1 to number of biomarkers in your
        # data
        #   dim: 1 x number of z-score stages
        # seq_init - intial ordering of the stages for each subtype
        # f_init - initial proprtion of individuals belonging to each subtype
        # N_startpoints - the number of start points for the fitting
        # likelihood_flag - whether to use an exact method of inference - when set
        # to 'Exact', the exact method is used, the approximate method is used for
        # all other settings
        #
        # OUTPUTS:
        # ml_sequence - the ordering of the stages for each subtype for the next
        # SuStaIn model in the hierarchy
        # ml_f - the most probable proportion of individuals belonging to each
        # subtype for the next SuStaIn model in the hierarchy
        # ml_likelihood - the likelihood of the most probable SuStaIn model for the
        # next SuStaIn model in the hierarchy
        # previous outputs _mat - same as before but for each start point
        N_S                                 = seq_init.shape[0]
        terminate                           = 0
        startpoint                          = 0

        ml_sequence_mat                     = np.zeros((N_S, sustainData.getNumStages(), self.N_startpoints))
        ml_f_mat                            = np.zeros((N_S, self.N_startpoints))
        ml_likelihood_mat                   = np.zeros((self.N_startpoints, 1))
        while terminate == 0:
            print(' ++ startpoint', startpoint)

            this_ml_sequence,       \
            this_ml_f,              \
            this_ml_likelihood, _, _, _     = self._perform_em(sustainData, seq_init, f_init)

            ml_sequence_mat[:, :, startpoint] = this_ml_sequence
            ml_f_mat[:, startpoint]         = this_ml_f
            ml_likelihood_mat[startpoint]   = this_ml_likelihood

            if startpoint == (self.N_startpoints - 1):
                terminate                   = 1
            startpoint                      = startpoint + 1

        ix                                  = np.where(ml_likelihood_mat == max(ml_likelihood_mat))
        ix                                  = ix[0]

        ml_sequence                         = ml_sequence_mat[:, :, ix]
        ml_f                                = ml_f_mat[:, ix]
        ml_likelihood                       = ml_likelihood_mat[ix]

        return ml_sequence, ml_f, ml_likelihood, ml_sequence_mat, ml_f_mat, ml_likelihood_mat


    def _perform_em(self, sustainData, current_sequence, current_f):

        # Perform an E-M procedure to estimate parameters of SuStaIn model
        MaxIter                             = 100

        N                                   = sustainData.getNumStages()    #self.stage_zscore.shape[1]
        N_S                                 = current_sequence.shape[0]
        current_likelihood, _, _, _, _      = self._calculate_likelihood(sustainData, current_sequence, current_f)

        terminate                           = 0
        iteration                           = 0
        samples_sequence                    = np.nan * np.ones((MaxIter, N, N_S))
        samples_f                           = np.nan * np.ones((MaxIter, N_S))
        samples_likelihood                  = np.nan * np.ones((MaxIter, 1))

        samples_sequence[0, :, :]           = current_sequence.reshape(current_sequence.shape[1], current_sequence.shape[0])
        current_f                           = np.array(current_f).reshape(len(current_f))
        samples_f[0, :]                     = current_f
        samples_likelihood[0]               = current_likelihood
        while terminate == 0:

            candidate_sequence,     \
            candidate_f,            \
            candidate_likelihood            = self._optimise_parameters(sustainData, current_sequence, current_f)

            HAS_converged                   = np.fabs((candidate_likelihood - current_likelihood) / max(candidate_likelihood, current_likelihood)) < 1e-6
            if HAS_converged:
                #print('EM converged in', iteration + 1, 'iterations')
                terminate                   = 1
            else:
                if candidate_likelihood > current_likelihood:
                    current_sequence        = candidate_sequence
                    current_f               = candidate_f
                    current_likelihood      = candidate_likelihood

            samples_sequence[iteration, :, :] = current_sequence.T.reshape(current_sequence.T.shape[0], N_S)
            samples_f[iteration, :]         = current_f
            samples_likelihood[iteration]   = current_likelihood

            if iteration == (MaxIter - 1):
                terminate                   = 1
            iteration                       = iteration + 1

        ml_sequence                         = current_sequence
        ml_f                                = current_f
        ml_likelihood                       = current_likelihood
        return ml_sequence, ml_f, ml_likelihood, samples_sequence, samples_f, samples_likelihood

    def _calculate_likelihood(self, sustainData, S, f):
        # Computes the likelihood of a mixture of linear z-score models using either
        # an approximate method (faster, default setting) or an exact method
        #
        #
        # OUTPUTS:
        # loglike - the log-likelihood of the current model
        # total_prob_subj - the total probability of the current SuStaIn model for
        # each subject
        # total_prob_stage - the total probability of each stage in the current
        # SuStaIn model
        # total_prob_cluster - the total probability of each subtype in the current
        # SuStaIn model
        # p_perm_k - the probability of each subjects data at each stage of each
        # subtype in the current SuStaIn model

        M                                   = sustainData.getNumSamples()  #data_local.shape[0]
        N_S                                 = S.shape[0]
        N                                   = sustainData.getNumStages()    #self.stage_zscore.shape[1]

        f                                   = np.array(f).reshape(N_S, 1, 1)
        f_val_mat                           = np.tile(f, (1, N + 1, M))
        f_val_mat                           = np.transpose(f_val_mat, (2, 1, 0))

        p_perm_k                            = np.zeros((M, N + 1, N_S))

        for s in range(N_S):
            p_perm_k[:, :, s]               = self._calculate_likelihood_stage(sustainData, S[s])  #self.__calculate_likelihood_stage_linearzscoremodel_approx(data_local, S[s])


        total_prob_cluster                  = np.squeeze(np.sum(p_perm_k * f_val_mat, 1))
        total_prob_stage                    = np.sum(p_perm_k * f_val_mat, 2)
        total_prob_subj                     = np.sum(total_prob_stage, 1)

        loglike                             = sum(np.log(total_prob_subj + 1e-250))

        return loglike, total_prob_subj, total_prob_stage, total_prob_cluster, p_perm_k

    def _estimate_uncertainty_sustain_model(self, sustainData, seq_init, f_init):

        # Estimate the uncertainty in the subtype progression patterns and
        # proportion of individuals belonging to the SuStaIn model
        #
        #
        # OUTPUTS:
        # ml_sequence - the most probable ordering of the stages for each subtype
        # found across MCMC samples
        # ml_f - the most probable proportion of individuals belonging to each
        # subtype found across MCMC samples
        # ml_likelihood - the likelihood of the most probable SuStaIn model found
        # across MCMC samples
        # samples_sequence - samples of the ordering of the stages for each subtype
        # obtained from MCMC sampling
        # samples_f - samples of the proportion of individuals belonging to each
        # subtype obtained from MCMC sampling
        # samples_likeilhood - samples of the likelihood of each SuStaIn model
        # sampled by the MCMC sampling

        # Perform a few initial passes where the perturbation sizes of the MCMC uncertainty estimation are tuned
        seq_sigma_opt, f_sigma_opt          = self._optimise_mcmc_settings(sustainData, seq_init, f_init)

        # Run the full MCMC algorithm to estimate the uncertainty
        ml_sequence,        \
        ml_f,               \
        ml_likelihood,      \
        samples_sequence,   \
        samples_f,          \
        samples_likelihood                  = self._perform_mcmc(sustainData, seq_init, f_init, self.N_iterations_MCMC, seq_sigma_opt, f_sigma_opt)

        return ml_sequence, ml_f, ml_likelihood, samples_sequence, samples_f, samples_likelihood

    def _optimise_mcmc_settings(self, sustainData, seq_init, f_init):

        # Optimise the perturbation size for the MCMC algorithm
        n_iterations_MCMC_optimisation      = int(1e4)  # FIXME: set externally

        n_passes_optimisation               = 3

        seq_sigma_currentpass               = 1
        f_sigma_currentpass                 = 0.01  # magic number

        N_S                                 = seq_init.shape[0]

        for i in range(n_passes_optimisation):

            _, _, _, samples_sequence_currentpass, samples_f_currentpass, _ = self._perform_mcmc(   sustainData,
                                                                                                     seq_init,
                                                                                                     f_init,
                                                                                                     n_iterations_MCMC_optimisation,
                                                                                                     seq_sigma_currentpass,
                                                                                                     f_sigma_currentpass)

            samples_position_currentpass    = np.zeros(samples_sequence_currentpass.shape)
            for s in range(N_S):
                for sample in range(n_iterations_MCMC_optimisation):
                    temp_seq                        = samples_sequence_currentpass[s, :, sample]
                    temp_inv                        = np.array([0] * samples_sequence_currentpass.shape[1])
                    temp_inv[temp_seq.astype(int)]  = np.arange(samples_sequence_currentpass.shape[1])
                    samples_position_currentpass[s, :, sample] = temp_inv

            seq_sigma_currentpass           = np.std(samples_position_currentpass, axis=2, ddof=1)  # np.std is different to Matlab std, which normalises to N-1 by default
            seq_sigma_currentpass[seq_sigma_currentpass < 0.01] = 0.01  # magic number

            f_sigma_currentpass             = np.std(samples_f_currentpass, axis=1, ddof=1)         # np.std is different to Matlab std, which normalises to N-1 by default

        seq_sigma_opt                       = seq_sigma_currentpass
        f_sigma_opt                         = f_sigma_currentpass

        return seq_sigma_opt, f_sigma_opt

    def _evaluate_likelihood_setofsamples(self, sustainData, samples_sequence, samples_f):

        # Take MCMC samples of the uncertainty in the SuStaIn model parameters
        M                                   = sustainData.getNumSamples()   #data_local.shape[0]
        n_iterations                        = samples_sequence.shape[2]
        samples_likelihood_subj             = np.zeros((M, n_iterations))
        for i in range(n_iterations):
            S                               = samples_sequence[:, :, i]
            f                               = samples_f[:, i]

            _, likelihood_sample_subj, _, _, _  = self._calculate_likelihood(sustainData, S, f)

            samples_likelihood_subj[:, i]   = likelihood_sample_subj

        return samples_likelihood_subj


    # ********************* ABSTRACT METHODS
    @abstractmethod
    def _initialise_sequence(self):
        pass

    @abstractmethod
    def _calculate_likelihood_stage(self, sustainData, S):
        pass

    @abstractmethod
    def _optimise_parameters(self, sustainData, S_init, f_init):
        pass

    @abstractmethod
    def _perform_mcmc(self, sustainData, seq_init, f_init, n_iterations, seq_sigma, f_sigma):
        pass

    @abstractmethod
    def _plot_sustain_model(self, samples_sequence, samples_f, subtype, samples_likelihood, n_samples, cval=False):
        pass

    # ********************* STATIC METHODS
    @staticmethod
    def calc_coeff(sig):
        return 1. / np.sqrt(np.pi * 2.0) * sig

    @staticmethod
    def calc_exp(x, mu, sig):
        x = (x - mu) / sig
        return np.exp(-.5 * x * x)