"""
Neuraxle Tensorflow V2 Utility classes
=========================================
Neuraxle utility classes for tensorflow v2.

..
    Copyright 2019, Neuraxio Inc.
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

import tensorflow as tf
from neuraxle.base import BaseSaver, BaseStep, ExecutionContext
from neuraxle.hyperparams.space import HyperparameterSamples, HyperparameterSpace

from neuraxle_tensorflow.tensorflow import BaseTensorflowModelStep


class Tensorflow2ModelStep(BaseTensorflowModelStep):
    """
    Base class for tensorflow 2 steps.
    It uses :class:`TensorflowV2StepSaver` for saving the model.

    .. seealso::
        `Using the checkpoint model format <https://www.tensorflow.org/guide/checkpoint>`_,
        :class:`~neuraxle.base.BaseStep`
    """
    HYPERPARAMS = HyperparameterSamples({})
    HYPERPARAMS_SPACE = HyperparameterSpace({})

    def __init__(
            self,
            create_model,
            create_loss,
            create_optimizer,
            tf_model_checkpoint_folder=None
    ):
        BaseTensorflowModelStep.__init__(
            self,
            create_model=create_model,
            create_loss=create_loss,
            create_optimizer=create_optimizer,
            step_saver=TensorflowV2StepSaver()
        )

        if tf_model_checkpoint_folder is None:
            tf_model_checkpoint_folder = 'tensorflow_ckpts'
        self.tf_model_checkpoint_folder = tf_model_checkpoint_folder

    def setup(self) -> BaseStep:
        """
        Setup optimizer, model, and checkpoints for saving.

        :return: step
        :rtype: BaseStep
        """
        if self.is_initialized:
            return self

        self.optimizer = self.create_optimizer(self)
        self.model = self.create_model(self)

        self.checkpoint = tf.train.Checkpoint(step=tf.Variable(1), optimizer=self.optimizer, net=self.model)
        self.checkpoint_manager = tf.train.CheckpointManager(
            self.checkpoint,
            self.tf_model_checkpoint_folder,
            max_to_keep=3
        )

        self.is_initialized = True

        return self

    def strip(self):
        """
        Strip tensorflow 2 properties from to step to make it serializable.

        :return:
        """
        self.optimizer = None
        self.model = None
        self.checkpoint = None
        self.checkpoint_manager = None

    def fit(self, data_inputs, expected_outputs=None) -> 'BaseStep':
        x = tf.convert_to_tensor(data_inputs)
        y = tf.convert_to_tensor(expected_outputs)

        with tf.GradientTape() as tape:
            output = self.model(x)
            self.loss = self.create_loss(self, y, output)

        self.optimizer.apply_gradients(zip(
            tape.gradient(self.loss, self.model.trainable_variables),
            self.model.trainable_variables
        ))

        return self

    def transform(self, data_inputs):
        return self.model(tf.convert_to_tensor(data_inputs)).numpy()


class TensorflowV2StepSaver(BaseSaver):
    """
    Step saver for a tensorflow Session using tf.train.Checkpoint().
    It saves, or restores the tf.Session() checkpoint at the context path using the step name as file name.

    .. seealso::
        `Using the checkpoint model format <https://www.tensorflow.org/guide/checkpoint>`_
        :class:`~neuraxle.base.BaseSaver`
    """

    def save_step(self, step: 'Tensorflow2ModelStep', context: 'ExecutionContext') -> 'BaseStep':
        """
        Save a step that is using tf.train.Saver().

        :param step: step to save
        :type step: BaseStep
        :param context: execution context to save from
        :type context: ExecutionContext
        :return: saved step
        """
        step.checkpoint_manager.save()
        step.strip()
        return step

    def load_step(self, step: 'Tensorflow2ModelStep', context: 'ExecutionContext') -> 'BaseStep':
        """
        Load a step that is using tensorflow using tf.train.Checkpoint().

        :param step: step to load
        :type step: BaseStep
        :param context: execution context to load from
        :type context: ExecutionContext
        :return: loaded step
        """
        step.is_initialized = False
        step.setup()
        step.checkpoint.restore(step.checkpoint_manager.latest_checkpoint)
        return step

    def can_load(self, step: 'Tensorflow2ModelStep', context: 'ExecutionContext') -> bool:
        """
        Returns whether or not we can load.

        :param step: step to load
        :type step: BaseStep
        :param context: execution context to load from
        :type context: ExecutionContext
        :return: loaded step
        """
        return True