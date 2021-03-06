# Copyright (c) 2020, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import tempfile

import onnx
import pytest
import pytorch_lightning as pl
import wget
from omegaconf import DictConfig, OmegaConf

from nemo.collections import nlp as nemo_nlp
from nemo.collections.nlp.models import IntentSlotClassificationModel
from nemo.collections.nlp.modules.common import (
    BertPretrainingTokenClassifier,
    SequenceClassifier,
    SequenceRegression,
    SequenceTokenClassifier,
    TokenClassifier,
)


def classifier_export(obj):
    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.join(tmpdir, obj.__class__.__name__ + '.onnx')
        obj = obj.cuda()
        obj.export(output=filename)


class TestExportableClassifiers:
    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_token_classifier_export_to_onnx(self):
        for num_layers in [1, 2, 4]:
            classifier_export(TokenClassifier(hidden_size=256, num_layers=num_layers, num_classes=16))

    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_bert_pretraining_export_to_onnx(self):
        for num_layers in [1, 2, 4]:
            classifier_export(TokenClassifier(hidden_size=256, num_layers=num_layers, num_classes=16))

    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_sequence_token_classifier_export_to_onnx(self):
        for num_layers in [1, 2, 4]:
            classifier_export(
                SequenceTokenClassifier(hidden_size=256, num_slots=8, num_intents=8, num_layers=num_layers)
            )

    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_sequence_classifier_export_to_onnx(self):
        for num_layers in [1, 2, 4]:
            classifier_export(SequenceClassifier(hidden_size=256, num_classes=16, num_layers=num_layers))

    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_sequence_regression_export_to_onnx(self):
        for num_layers in [1, 2, 4]:
            classifier_export(SequenceRegression(hidden_size=256, num_layers=num_layers))

    @pytest.mark.run_only_on('GPU')
    @pytest.mark.unit
    def test_IntentSlotClassificationModel(self, dummy_data):
        with tempfile.TemporaryDirectory() as tmpdir:
            wget.download(
                'https://raw.githubusercontent.com/NVIDIA/NeMo/main/examples/'
                'nlp/intent_slot_classification/conf/intent_slot_classification_config.yaml',
                tmpdir,
            )
            config_file = os.path.join(tmpdir, 'intent_slot_classification_config.yaml')
            config = OmegaConf.load(config_file)
            config = OmegaConf.create(OmegaConf.to_container(config, resolve=True))
            config.model.data_dir = dummy_data
            config.trainer.gpus = 1
            config.trainer.precision = 32
            config.trainer.accelerator = None
            trainer = pl.Trainer(**config.trainer)
            model = IntentSlotClassificationModel(config.model, trainer=trainer)
            filename = os.path.join(tmpdir, 'isc.onnx')
            model.export(output=filename)
            onnx_model = onnx.load(filename)
            onnx.checker.check_model(onnx_model, full_check=True)  # throws when failed
            assert len(onnx_model.graph.node) == 1167
            assert onnx_model.graph.node[0].name == 'Unsqueeze_0'
            assert onnx_model.graph.node[30].name == 'Add_30'
            assert onnx_model.graph.node[1165].name == 'ISCMatMul_8'
            assert onnx_model.graph.input[0].name == 'input_ids'
            assert onnx_model.graph.input[1].name == 'attention_mask'
            assert onnx_model.graph.input[2].name == 'token_type_ids'
            assert onnx_model.graph.output[0].name == 'intent_logits'
            assert onnx_model.graph.output[1].name == 'slot_logits'

    def test_TokenClassificationModel_export_to_onnx(self):
        model = nemo_nlp.models.TokenClassificationModel.from_pretrained(model_name="NERModel")
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, 'ner.onnx')
            model.export(output=filename)
            onnx_model = onnx.load(filename)
            onnx.checker.check_model(onnx_model, full_check=True)  # throws when failed
            assert len(onnx_model.graph.node) == 1163
            assert onnx_model.graph.node[0].name == 'Unsqueeze_0'
            assert onnx_model.graph.node[1162].name == 'TKCLLogSoftmax_5'
            assert onnx_model.graph.node[30].name == 'Add_30'
            assert onnx_model.graph.input[0].name == 'input_ids'
            assert onnx_model.graph.output[0].name == 'logits'

    def test_PunctuationCapitalizationModel_export_to_onnx(self):
        model = nemo_nlp.models.PunctuationCapitalizationModel.from_pretrained(
            model_name="Punctuation_Capitalization_with_BERT"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, 'puncap.onnx')
            punct_filename = os.path.join(tmpdir, 'punct_puncap.onnx')
            capit_filename = os.path.join(tmpdir, 'capit_puncap.onnx')
            model.export(output=filename)
            onnx_model = onnx.load(punct_filename)
            onnx.checker.check_model(onnx_model, full_check=True)  # throws when failed
            assert len(onnx_model.graph.node) == 1160
            assert onnx_model.graph.node[0].name == 'Unsqueeze_0'
            assert onnx_model.graph.node[1159].name == 'PTCLLogSoftmax_2'
            assert onnx_model.graph.node[30].name == 'Add_30'
            assert onnx_model.graph.input[0].name == 'input_ids'
            assert onnx_model.graph.input[2].name == 'token_type_ids'
            assert onnx_model.graph.output[0].name == 'logits'
            onnx_model = onnx.load(capit_filename)
            onnx.checker.check_model(onnx_model, full_check=True)  # throws when failed
            assert len(onnx_model.graph.node) == 1160
            assert onnx_model.graph.node[0].name == 'Unsqueeze_0'
            assert onnx_model.graph.node[1159].name == 'CPCLLogSoftmax_2'
            assert onnx_model.graph.node[30].name == 'Add_30'
            assert onnx_model.graph.input[0].name == 'input_ids'
            assert onnx_model.graph.input[2].name == 'token_type_ids'
            assert onnx_model.graph.output[0].name == 'logits'

    def test_QAModel_export_to_onnx(self):
        model = nemo_nlp.models.QAModel.from_pretrained(model_name="BERTBaseUncasedSQuADv1.1")
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, 'qa.onnx')
            model.export(output=filename)
            onnx_model = onnx.load(filename)
            onnx.checker.check_model(onnx_model, full_check=True)  # throws when failed
            assert len(onnx_model.graph.node) == 1159
            assert onnx_model.graph.node[0].name == 'Unsqueeze_0'
            assert onnx_model.graph.node[1158].name == 'QAAdd_1'
            assert onnx_model.graph.node[30].name == 'Add_30'
            assert onnx_model.graph.input[0].name == 'input_ids'
            assert onnx_model.graph.input[2].name == 'token_type_ids'
            assert onnx_model.graph.output[0].name == 'logits'


@pytest.fixture()
def dummy_data(test_data_dir):
    return os.path.join(test_data_dir, 'nlp', 'dummy_data')
