# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors.
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


import random
import unittest

from transformers import is_torch_available

from .test_configuration_common import ConfigTester
from .test_modeling_common import ModelTesterMixin, ids_tensor
from .utils import CACHE_DIR, require_torch, slow, torch_device


if is_torch_available():
    import torch
    from transformers import TransfoXLConfig, TransfoXLModel, TransfoXLLMHeadModel
    from transformers.modeling_transfo_xl import TRANSFO_XL_PRETRAINED_MODEL_ARCHIVE_MAP


@require_torch
class TransfoXLModelTest(ModelTesterMixin, unittest.TestCase):

    all_model_classes = (TransfoXLModel, TransfoXLLMHeadModel) if is_torch_available() else ()
    all_generative_model_classes = (TransfoXLLMHeadModel,) if is_torch_available() else ()
    test_pruning = False
    test_torchscript = False
    test_resize_embeddings = False

    class TransfoXLModelTester(object):
        def __init__(
            self,
            parent,
            batch_size=13,
            seq_length=7,
            mem_len=30,
            clamp_len=15,
            is_training=True,
            use_labels=True,
            vocab_size=99,
            cutoffs=[10, 50, 80],
            hidden_size=32,
            d_embed=32,
            num_attention_heads=4,
            d_head=8,
            d_inner=128,
            div_val=2,
            num_hidden_layers=5,
            scope=None,
            seed=1,
            eos_token_id=0,
        ):
            self.parent = parent
            self.batch_size = batch_size
            self.seq_length = seq_length
            self.mem_len = mem_len
            self.key_length = seq_length + mem_len
            self.clamp_len = clamp_len
            self.is_training = is_training
            self.use_labels = use_labels
            self.vocab_size = vocab_size
            self.cutoffs = cutoffs
            self.hidden_size = hidden_size
            self.d_embed = d_embed
            self.num_attention_heads = num_attention_heads
            self.d_head = d_head
            self.d_inner = d_inner
            self.div_val = div_val
            self.num_hidden_layers = num_hidden_layers
            self.scope = scope
            self.seed = seed
            self.eos_token_id = eos_token_id

        def prepare_config_and_inputs(self):
            input_ids_1 = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)
            input_ids_2 = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

            lm_labels = None
            if self.use_labels:
                lm_labels = ids_tensor([self.batch_size, self.seq_length], self.vocab_size)

            config = TransfoXLConfig(
                vocab_size=self.vocab_size,
                mem_len=self.mem_len,
                clamp_len=self.clamp_len,
                cutoffs=self.cutoffs,
                d_model=self.hidden_size,
                d_embed=self.d_embed,
                n_head=self.num_attention_heads,
                d_head=self.d_head,
                d_inner=self.d_inner,
                div_val=self.div_val,
                n_layer=self.num_hidden_layers,
                eos_token_ids=self.eos_token_id,
            )

            return (config, input_ids_1, input_ids_2, lm_labels)

        def set_seed(self):
            random.seed(self.seed)
            torch.manual_seed(self.seed)

        def create_transfo_xl_model(self, config, input_ids_1, input_ids_2, lm_labels):
            model = TransfoXLModel(config)
            model.to(torch_device)
            model.eval()

            hidden_states_1, mems_1 = model(input_ids_1)
            hidden_states_2, mems_2 = model(input_ids_2, mems_1)
            outputs = {
                "hidden_states_1": hidden_states_1,
                "mems_1": mems_1,
                "hidden_states_2": hidden_states_2,
                "mems_2": mems_2,
            }
            return outputs

        def check_transfo_xl_model_output(self, result):
            self.parent.assertListEqual(
                list(result["hidden_states_1"].size()), [self.batch_size, self.seq_length, self.hidden_size]
            )
            self.parent.assertListEqual(
                list(result["hidden_states_2"].size()), [self.batch_size, self.seq_length, self.hidden_size]
            )
            self.parent.assertListEqual(
                list(list(mem.size()) for mem in result["mems_1"]),
                [[self.mem_len, self.batch_size, self.hidden_size]] * self.num_hidden_layers,
            )
            self.parent.assertListEqual(
                list(list(mem.size()) for mem in result["mems_2"]),
                [[self.mem_len, self.batch_size, self.hidden_size]] * self.num_hidden_layers,
            )

        def create_transfo_xl_lm_head(self, config, input_ids_1, input_ids_2, lm_labels):
            model = TransfoXLLMHeadModel(config)
            model.to(torch_device)
            model.eval()

            lm_logits_1, mems_1 = model(input_ids_1)
            loss_1, _, mems_1 = model(input_ids_1, labels=lm_labels)
            lm_logits_2, mems_2 = model(input_ids_2, mems=mems_1)
            loss_2, _, mems_2 = model(input_ids_2, labels=lm_labels, mems=mems_1)

            outputs = {
                "loss_1": loss_1,
                "mems_1": mems_1,
                "lm_logits_1": lm_logits_1,
                "loss_2": loss_2,
                "mems_2": mems_2,
                "lm_logits_2": lm_logits_2,
            }
            return outputs

        def check_transfo_xl_lm_head_output(self, result):
            self.parent.assertListEqual(list(result["loss_1"].size()), [self.batch_size, self.seq_length])
            self.parent.assertListEqual(
                list(result["lm_logits_1"].size()), [self.batch_size, self.seq_length, self.vocab_size]
            )
            self.parent.assertListEqual(
                list(list(mem.size()) for mem in result["mems_1"]),
                [[self.mem_len, self.batch_size, self.hidden_size]] * self.num_hidden_layers,
            )

            self.parent.assertListEqual(list(result["loss_2"].size()), [self.batch_size, self.seq_length])
            self.parent.assertListEqual(
                list(result["lm_logits_2"].size()), [self.batch_size, self.seq_length, self.vocab_size]
            )
            self.parent.assertListEqual(
                list(list(mem.size()) for mem in result["mems_2"]),
                [[self.mem_len, self.batch_size, self.hidden_size]] * self.num_hidden_layers,
            )

        def prepare_config_and_inputs_for_common(self):
            config_and_inputs = self.prepare_config_and_inputs()
            (config, input_ids_1, input_ids_2, lm_labels) = config_and_inputs
            inputs_dict = {"input_ids": input_ids_1}
            return config, inputs_dict

    def setUp(self):
        self.model_tester = TransfoXLModelTest.TransfoXLModelTester(self)
        self.config_tester = ConfigTester(self, config_class=TransfoXLConfig, d_embed=37)

    def test_config(self):
        self.config_tester.run_common_tests()

    def test_transfo_xl_model(self):
        self.model_tester.set_seed()
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        output_result = self.model_tester.create_transfo_xl_model(*config_and_inputs)
        self.model_tester.check_transfo_xl_model_output(output_result)

    def test_transfo_xl_lm_head(self):
        self.model_tester.set_seed()
        config_and_inputs = self.model_tester.prepare_config_and_inputs()
        output_result = self.model_tester.create_transfo_xl_lm_head(*config_and_inputs)
        self.model_tester.check_transfo_xl_lm_head_output(output_result)

    @slow
    def test_model_from_pretrained(self):
        for model_name in list(TRANSFO_XL_PRETRAINED_MODEL_ARCHIVE_MAP.keys())[:1]:
            model = TransfoXLModel.from_pretrained(model_name, cache_dir=CACHE_DIR)
            self.assertIsNotNone(model)


class TransfoXLModelLanguageGenerationTest(unittest.TestCase):
    @slow
    def test_lm_generate_transfo_xl_wt103(self):
        model = TransfoXLLMHeadModel.from_pretrained("transfo-xl-wt103")
        input_ids = torch.Tensor(
            [
                [
                    33,
                    1297,
                    2,
                    1,
                    1009,
                    4,
                    1109,
                    11739,
                    4762,
                    358,
                    5,
                    25,
                    245,
                    22,
                    1706,
                    17,
                    20098,
                    5,
                    3215,
                    21,
                    37,
                    1110,
                    3,
                    13,
                    1041,
                    4,
                    24,
                    603,
                    490,
                    2,
                    71477,
                    20098,
                    104447,
                    2,
                    20961,
                    1,
                    2604,
                    4,
                    1,
                    329,
                    3,
                    6224,
                    831,
                    16002,
                    2,
                    8,
                    603,
                    78967,
                    29546,
                    23,
                    803,
                    20,
                    25,
                    416,
                    5,
                    8,
                    232,
                    4,
                    277,
                    6,
                    1855,
                    4601,
                    3,
                    29546,
                    54,
                    8,
                    3609,
                    5,
                    57211,
                    49,
                    4,
                    1,
                    277,
                    18,
                    8,
                    1755,
                    15691,
                    3,
                    341,
                    25,
                    416,
                    693,
                    42573,
                    71,
                    17,
                    401,
                    94,
                    31,
                    17919,
                    2,
                    29546,
                    7873,
                    18,
                    1,
                    435,
                    23,
                    11011,
                    755,
                    5,
                    5167,
                    3,
                    7983,
                    98,
                    84,
                    2,
                    29546,
                    3267,
                    8,
                    3609,
                    4,
                    1,
                    4865,
                    1075,
                    2,
                    6087,
                    71,
                    6,
                    346,
                    8,
                    5854,
                    3,
                    29546,
                    824,
                    1400,
                    1868,
                    2,
                    19,
                    160,
                    2,
                    311,
                    8,
                    5496,
                    2,
                    20920,
                    17,
                    25,
                    15097,
                    3,
                    24,
                    24,
                    0,
                ]
            ]
        ).long()
        #  In 1991 , the remains of Russian Tsar Nicholas II and his family
        #  ( except for Alexei and Maria ) are discovered .
        #  The voice of Nicholas's young son , Tsarevich Alexei Nikolaevich , narrates the
        #  remainder of the story . 1883 Western Siberia ,
        #  a young Grigori Rasputin is asked by his father and a group of men to perform magic .
        #  Rasputin has a vision and denounces one of the men as a horse thief . Although his
        #  father initially slaps him for making such an accusation , Rasputin watches as the
        #  man is chased outside and beaten . Twenty years later , Rasputin sees a vision of
        #  the Virgin Mary , prompting him to become a priest . Rasputin quickly becomes famous ,
        #  with people , even a bishop , begging for his blessing . <eod> </s> <eos>

        expected_output_ids = [
            33,
            1297,
            2,
            1,
            1009,
            4,
            1109,
            11739,
            4762,
            358,
            5,
            25,
            245,
            22,
            1706,
            17,
            20098,
            5,
            3215,
            21,
            37,
            1110,
            3,
            13,
            1041,
            4,
            24,
            603,
            490,
            2,
            71477,
            20098,
            104447,
            2,
            20961,
            1,
            2604,
            4,
            1,
            329,
            3,
            6224,
            831,
            16002,
            2,
            8,
            603,
            78967,
            29546,
            23,
            803,
            20,
            25,
            416,
            5,
            8,
            232,
            4,
            277,
            6,
            1855,
            4601,
            3,
            29546,
            54,
            8,
            3609,
            5,
            57211,
            49,
            4,
            1,
            277,
            18,
            8,
            1755,
            15691,
            3,
            341,
            25,
            416,
            693,
            42573,
            71,
            17,
            401,
            94,
            31,
            17919,
            2,
            29546,
            7873,
            18,
            1,
            435,
            23,
            11011,
            755,
            5,
            5167,
            3,
            7983,
            98,
            84,
            2,
            29546,
            3267,
            8,
            3609,
            4,
            1,
            4865,
            1075,
            2,
            6087,
            71,
            6,
            346,
            8,
            5854,
            3,
            29546,
            824,
            1400,
            1868,
            2,
            19,
            160,
            2,
            311,
            8,
            5496,
            2,
            20920,
            17,
            25,
            15097,
            3,
            24,
            24,
            0,
            29546,
            40,
            1092,
            18,
            8,
            5854,
            7,
            1143,
            2,
            7,
            1,
            159,
            99,
            16,
            1,
            1009,
            4,
            1109,
            11739,
            4762,
            358,
            5,
            25,
            245,
            28,
            1110,
            3,
            57,
            629,
            38,
            3493,
            47,
            1094,
            7,
            1297,
            3,
            0,
        ]
        #  In 1991, the remains of Russian Tsar Nicholas II and his family (
        #  except for Alexei and Maria ) are discovered. The voice of young son,
        #  Tsarevich Alexei Nikolaevich, narrates the remainder of the story.
        #  1883 Western Siberia, a young Grigori Rasputin is asked by his father
        #  and a group of men to perform magic. Rasputin has a vision and
        #  denounces one of the men as a horse thief. Although his father initially
        #  slaps him for making such an accusation, Rasputin watches as the man
        #  is chased outside and beaten. Twenty years later, Rasputin sees a vision
        #  of the Virgin Mary, prompting him to become a priest.
        #  Rasputin quickly becomes famous, with people, even a bishop, begging for
        #  his blessing. Rasputin first appears as a priest in 1996, in the same year
        #  that the remains of Russian Tsar Nicholas II and his family were discovered. H

        torch.manual_seed(0)

        output_ids = model.generate(input_ids, max_length=200)
        self.assertListEqual(output_ids[0].tolist(), expected_output_ids)
