from sklearn.preprocessing import LabelEncoder, OneHotEncoder
import os
import numpy as np
from datetime import datetime
from scipy.sparse import rand
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, f1_score
import matplotlib.pyplot as plt
import optuna
from optuna.integration.wandb import WeightsAndBiasesCallback
import wandb
# import cupy as np


class ReservoirRewriteMulti:
    def __init__(self, reservoir=None, n_internal_units=None,
                 spectral_radiusList=None,  # list spectral radius list
                 leakList=None,  # list leak
                 connectivityList=None,  # list connectivitity
                 input_scaling=None,
                 noise_level=None,
                 n_drop=None,
                 w_ridge_embedding=None,    
                 w_ridge=None,  
                 multiple_reservoir_number=1):
        
        self.n_drop = n_drop
        self.list_reservoir_weight = []
        self.list_input_weight = []
        self.leakList = leakList

        # generate internal weight based on reservoir input number
        for ii in range(multiple_reservoir_number):
            # print (f'{self.leakList[ii]}')
            _reservoir = self._reservoir(n_internal_units=n_internal_units,
                                         spectral_radiusValue=spectral_radiusList[ii],
                                         leakValue=self.leakList[ii],
                                         connectivityValue=connectivityList[ii],
                                         input_scaling=input_scaling,
                                         noise_level=noise_level)
            self.list_reservoir_weight.append(_reservoir)
            
        print(f'{ "self.list_reservoir_weight.shape = ", np.asarray(self.list_reservoir_weight).shape}')    
        # Initialize ridge regression model
        self._ridge_embedding = Ridge(alpha=w_ridge_embedding, fit_intercept=True)
        # Initialize readout
        self.readout = Ridge(alpha=w_ridge)
        
    """generate reservoir node weight """
    def _reservoir(
            self,
            n_internal_units=100, 
            spectral_radiusValue=0.99, 
            leakValue=None,
            connectivityValue=0.3, 
            input_scaling=0.2, 
            noise_level=0.01,
                  ):
        
        # Initialize attributes
        self._n_internal_units = n_internal_units
        self._input_scaling = input_scaling
        self._noise_level = noise_level
        self._leak = leakValue

        """Input weights depend on input size: they are set when data is provided"""
        """self._input_weights     = None"""
        """generate reservoir internal weight""" 
        _internal_weights = self._initialize_internal_weights(
                n_internal_units,
                connectivityValue,
                spectral_radiusValue)
        
        return _internal_weights

    """train the reservoir based on weight that already generates on contructor class"""
    def train_reservoir(self, 
                        X, 
                        Y=None,
                        multiple_reservoir_number=0):
        
        tempX = X
        tempY = Y
        tempReservoirNumber = multiple_reservoir_number
        all_res_state = None 

        for ii in range(tempReservoirNumber):
            # generate input weight
            N, T, V = X.shape

            # print (f'{X.shape=}')

            _input_weights = (2.0 * np.random.binomial(1, 0.5, [self._n_internal_units, V]) - 1.0) * self._input_scaling
            self.list_input_weight.append(_input_weights)

            # print (f'{_input_weights.shape =}')
            # ============ Compute reservoir states ============ 
            _res_states = self._get_states(tempX, 
                                           leakValue=self.leakList[ii], 
                                           reservoirWeight=self.list_reservoir_weight[ii], 
                                           n_drop=self.n_drop,
                                           input_weight=self.list_input_weight[ii])
            if ii == 0:
                all_res_state = _res_states
            else:
                all_res_state = np.dstack((all_res_state, _res_states))

            print(f'{all_res_state.shape =}')

        # print (f'{all_res_state.shape =}')
        # ============ Generate representation of the MTS ============
        coeff_tr = []
        biases_tr = [] 
            
        # Reservoir model space representation
        for i in range(X.shape[0]):
            self._ridge_embedding.fit(all_res_state[i, 0:-1, :], all_res_state[i, 1:, :])
            # print (f'{self._ridge_embedding.coef_.ravel().shape}')
            # print (f'{self._ridge_embedding.coef_.shape}')
            # print (f'{self._ridge_embedding.intercept_.ravel().shape}')
            # print (f'{self._ridge_embedding.intercept_.shape}')
            coeff_tr.append(self._ridge_embedding.coef_.ravel())
            biases_tr.append(self._ridge_embedding.intercept_.ravel())
        input_repr = np.concatenate((np.vstack(coeff_tr), np.vstack(biases_tr)), axis=1)
            
        """
        if ii==0:
            all_res_state = input_repr
        else:
            all_res_state = np.concatenate((all_res_state, input_repr),axis=1)
            print (f'{all_res_state.shape =}')
        """
        # lyapunov_local, lyapunov_avg, lyapunov_max = self.local_lyapunov_exponent(all_res_state)
        # print(f'{lyapunov_avg =}, {lyapunov_max =}')
        # self.plot_local_lyapunov_exponent_heatmap(lyapunov_local)

        
        '''
        lyapunov_avg, lyapunov_cumsum = self.largest_lyapunov_exponent(all_res_state)
        print(f'{lyapunov_avg[-1] =}, {np.mean(lyapunov_avg) =}')
        '''
        # self.plot_lyapunov_exponent(lyapunov_cumsum)
        # print (f'{input_repr.shape = }' )
        # ============ Apply readout ============
        # Ridge regression
        test = self.readout.fit(input_repr, tempY) 
        # print (f'{"self.readout =",self.readout}')
        coefficients = self.readout.coef_
        # print (f'{"coefficients shape= ",coefficients.shape}')

        ''' magnitude = self.compute_fourier_transform(all_res_state)
        self.plot_fourier_transform(magnitude, title="Fourier Transform of Reservoir Size 3*170")
        self.plot_all_magnitudes(magnitude,  title="Fourier Transform of Reservoir Size 3*170")
        return lyapunov_avg
        '''
        

    def test_reservoir(self,
                       Xte, 
                       Yte=None,
                       multiple_reservoir_number=0):
                    
        all_input_repr_te = None
        # print (f'{np.asmatrix (self.list_input_weight).shape}')

        for ii in range(multiple_reservoir_number):
            # ============ Compute reservoir states ============
            res_states_te = self._get_states(Xte,
                                             leakValue=self.leakList[ii], 
                                             reservoirWeight=self.list_reservoir_weight[ii], 
                                             n_drop=self.n_drop,
                                             input_weight=self.list_input_weight[ii])
            # Skip dimensionality reduction

            if ii == 0:
                all_input_repr_te = res_states_te
            else:
                all_input_repr_te = np.dstack((all_input_repr_te, 
                                               res_states_te))
            
            """print (f'{all_input_repr_te.shape =}')"""

        """============ Generate representation of the MTS ============"""
        coeff_te = []
        biases_te = []   

        for i in range(Xte.shape[0]):
            self._ridge_embedding.fit(all_input_repr_te[i, 0:-1, :], all_input_repr_te[i, 1:, :])
            coeff_te.append(self._ridge_embedding.coef_.ravel())
            biases_te.append(self._ridge_embedding.intercept_.ravel())
        input_repr_te = np.concatenate((np.vstack(coeff_te), np.vstack(biases_te)), axis=1)

        """ 
        if ii==0:
             all_input_repr_te = input_repr_te
         else:
             all_input_repr_te = np.concatenate((all_input_repr_te, input_repr_te),axis=1)
             print(f'{all_input_repr_te.shape =}')
        """
        logits = self.readout.predict(input_repr_te)
        # print (f'{logits.shape =}')

        pred_class = np.argmax(logits, axis=1)
        # print (f'{pred_class.shape =}')
        accuracy, f1 = self._compute_test_scores(pred_class, Yte)
        return accuracy, f1

    def _compute_test_scores(self, pred_class, Yte):
        """
        Wrapper to compute classification accuracy and F1 score
        """
        
        true_class = np.argmax(Yte, axis=1)
        
        accuracy = accuracy_score(true_class, pred_class)
        if Yte.shape[1] > 2:
            f1 = f1_score(true_class, pred_class, average='weighted')
        else:
            f1 = f1_score(true_class, pred_class, average='binary')

        return accuracy, f1     

    def _initialize_internal_weights(self, 
                                     n_internal_units,
                                     connectivityValue, 
                                     spectral_radiusValue):

        '''Generate sparse matrix, uniformly distributed weights.'''
        internal_weights = rand(n_internal_units,
                                n_internal_units,
                                density=connectivityValue).todense()

        """Ensure that the nonzero values are uniformly distributed in [-0.5, 0.5]"""
        internal_weights[np.where(internal_weights > 0)] -= 0.5
        
        """Adjust the spectral radius."""
        E, _ = np.linalg.eig(internal_weights)
        e_max = np.max(np.abs(E))
        internal_weights /= np.abs(e_max)/spectral_radiusValue       

        return internal_weights

    def _get_states(self, X, leakValue=None, reservoirWeight=None, 
                    n_drop=0, 
                    input_weight=None):
        
        '''compute sequence of reservoir states'''
        states = self._compute_state_matrix(X, leakValue, 
                                            reservoirWeight=reservoirWeight, 
                                            input_weights=input_weight,
                                            n_drop=n_drop)
    
        return states
    
    def _compute_state_matrix(self, X, leakValue=None, reservoirWeight=None, 
                              input_weights=0, 
                              n_drop=0):
        N, T, _ = X.shape
        previous_state = np.zeros((N, self._n_internal_units), dtype=float)

        # Storage
        state_matrix = np.empty((N, T - n_drop, self._n_internal_units), dtype=float)

        for t in range(T):
            current_input = X[:, t, :]
            """print (f'{current_input.shape = }')"""
            """print(type(reservoirWeight))"""

            """Calculate state"""
            state_before_tanh = reservoirWeight.dot(previous_state.T) + input_weights.dot(current_input.T)

            """Add noise"""
            state_before_tanh += np.random.rand(self._n_internal_units, N)*self._noise_level

            """Apply nonlinearity and leakage (optional)"""
            if leakValue is None:
                previous_state = np.tanh(state_before_tanh).T
            else:
                previous_state = (1.0 - leakValue)*previous_state + np.tanh(state_before_tanh).T

            """Store everything after the dropout period"""
            if (t > n_drop - 1):
                state_matrix[:, t - n_drop, :] = previous_state
            # else:
            # state_matrix = previous_state
        return state_matrix

def main_function(trial):
    """10 class 78 frames"""
    pathWorkspace = '/home/bra1n/Documents/signLanguage/paperNeuralComputing'
    fileNameNpy = 'DataSaveOnNumpy/{}AllFrame_WLASL_100Class_option2.npy'.format

    pathKeypointTraining = os.path.join(pathWorkspace, fileNameNpy('Training'))
    pathLabelTraining = os.path.join(pathWorkspace, fileNameNpy('TrainingLabel'))
    pathKeypointVal = os.path.join(pathWorkspace, fileNameNpy('Validation'))
    pathLabelVal = os.path.join(pathWorkspace, fileNameNpy('ValidationLabel'))
    pathKeypointTest = os.path.join(pathWorkspace, fileNameNpy('Testing'))
    pathLabelTest = os.path.join(pathWorkspace, fileNameNpy('TestingLabel'))
    
    X_train = np.load(pathKeypointTraining, allow_pickle=True)
    y_train = np.load(pathLabelTraining, allow_pickle=True)
    X_val = np.load(pathKeypointVal, allow_pickle=True)
    y_val = np.load(pathLabelVal, allow_pickle=True)
    X_test = np.load(pathKeypointTest, allow_pickle=True)
    y_test = np.load(pathLabelTest, allow_pickle=True)

    # convert String into integer encode
    labelEncoder = LabelEncoder()
    y_train_labelEncoder = labelEncoder.fit_transform(y_train)
    y_val_labelEncoder = labelEncoder.fit_transform(y_val)
    y_test_labelEncoder = labelEncoder.fit_transform(y_test)

    # convert integer encode into binary
    oneHotEncoder = OneHotEncoder(sparse_output=False)
    yTrainLabel_integer_encode = y_train_labelEncoder.reshape(len(y_train_labelEncoder),1)
    yTrainLabel_onehot_encode = oneHotEncoder.fit_transform(yTrainLabel_integer_encode)

    yValLabel_integer_encode = y_val_labelEncoder.reshape(len(y_val_labelEncoder),1)
    yValLabel_onehot_encode = oneHotEncoder.fit_transform(yValLabel_integer_encode)

    yTestLabel_integer_encode = y_test_labelEncoder.reshape(len(y_test_labelEncoder),1)
    yTestLabel_onehot_encode = oneHotEncoder.fit_transform(yTestLabel_integer_encode)

    # print (f'{X_train.shape =}')
    configParam = {}
    
    # Hyperarameters of the reservoir
    configParam['n_internal_units'] = trial.suggest_int("n_internal_units", 50, 250, log=True) 
    configParam['spectral_radius'] = [0.177, 0.177]  # [trial.suggest_float("spectral_radius", 0.1, 1, log=True)] 
    configParam['leakList'] = [trial.suggest_float("leakList1", 0.1, 1, log=True), 
                               trial.suggest_float("leakList2", 0.1, 1, log=True)] 
    configParam['connectivity'] = [0.224, 0.224]  # [trial.suggest_float("connectivity", 0.1, 1, log=True)] 
    configParam['input_scaling'] = 0.2273  # [trial.suggest_float("input_scaling", 0.1, 1, log=True)] 
    configParam['noise_level'] = 0.132  # trial.suggest_float("noise_level", 0.1, 1, log=True)  
    configParam['n_drop'] = 0  # transient states to be dropped
  
    configParam['w_ridge_embedding'] = 27  # trial.suggest_int("w_ridge_embedding", 1, 50, log=True) 
    # Type of readout
    configParam['readout_type'] = 'lin'  # readout used for classification: {'lin', 'mlp', 'svm'}
    # Linear readout hyperparameters
    configParam['w_ridge'] = 1  # trial.suggest_int("w_ridge", 1, 50, log=True)  
    configParam['multiple_reservoir_number'] = 2  # minimum 1
    configParam['repeat'] = 1  # minimum 1
    # print(configParam)
    all_training_time = list()
    all_testing_time = list()

    #######
    listAccuracy = []
    listF1 = []
    maxAccuracy = 0

    for ii in range(configParam['repeat']): 
        # print (f'iterate {ii = }')
        start_time = datetime.now()
        classifier = ReservoirRewriteMulti(
                        reservoir=None,     
                        n_internal_units=configParam['n_internal_units'],
                        spectral_radiusList=configParam['spectral_radius'],
                        leakList=configParam['leakList'],
                        connectivityList=configParam['connectivity'],
                        input_scaling=configParam['input_scaling'],
                        noise_level=configParam['noise_level'],
                        n_drop=configParam['n_drop'],
                        w_ridge_embedding=configParam['w_ridge_embedding'],        
                        w_ridge=configParam['w_ridge'],           
                        multiple_reservoir_number=configParam['multiple_reservoir_number']) 
        
        classifier.train_reservoir(X_train, 
                                   Y=yTrainLabel_onehot_encode,
                                   multiple_reservoir_number=configParam['multiple_reservoir_number'])
        # print('Training time = %.2f seconds'%tr_time)
        end_time = datetime.now()
        durationTrainingTime = end_time - start_time
        
        start_time = datetime.now()
        # accuracy, f1 = classifier.test_reservoir(X_test, 
        #                                          Yte=yTestLabel_onehot_encode, 
        #                                          multiple_reservoir_number=configParam['multiple_reservoir_number'] )

        accuracy, f1 = classifier.test_reservoir(X_val, 
                                                 Yte=yValLabel_onehot_encode, 
                                                 multiple_reservoir_number=configParam['multiple_reservoir_number'] )
        
        end_time = datetime.now()
        durationTestingTime = end_time - start_time

        # print('Accuracy = %.3f, F1 = %.3f'%(accuracy, f1, ))
        # print (f'{accuracy =} ; {f1 =}; durationTraining = {durationTrainingTime} ; durationTesting = {durationTestingTime}')
        listAccuracy.append(accuracy)
        listF1.append(f1)
        all_training_time.append(durationTrainingTime)
        all_testing_time.append(durationTestingTime)

        if accuracy > maxAccuracy:
            maxAccuracy = accuracy

    meanTrainingTime = np.mean(all_training_time)
    meanTestingTime = np.mean(all_testing_time)
    mean, std = np.mean(listAccuracy), np.std(listAccuracy)
    print(f'{maxAccuracy =} ; {mean =}; {std =} ; {meanTrainingTime} ; {meanTestingTime}')
    '''  '''

    return mean


if __name__ == '__main__':   

    samplers = (
        optuna.samplers.RandomSampler,
        optuna.samplers.TPESampler,
    )

    num_runs = 5
    n_trials = 10

    for sampler in samplers:
        for _ in range(num_runs):
            wandb_kwargs = {
                "project": "multiple_reservoirs",
                "entity": "army",
                "config": {"sampler": sampler.__name__},
                "reinit": True,
            }

            wandbc = WeightsAndBiasesCallback(
                metric_name="val_accuracy", wandb_kwargs=wandb_kwargs
            )

            study = optuna.create_study(direction="maximize", sampler=sampler())
            study.optimize(main_function, n_trials=n_trials, callbacks=[wandbc])

            f = "best_{}".format
            for param_name, param_value in study.best_trial.params.items():
                wandb.run.summary[f(param_name)] = param_value

            wandb.run.summary["best accuracy"] = study.best_trial.value

            wandb.log(
                {
                    "optuna_optimization_history": optuna.visualization.plot_optimization_history(
                        study
                    ),
                    "optuna_param_importances": optuna.visualization.plot_param_importances(
                        study
                    ),
                }
            )

            wandb.finish()