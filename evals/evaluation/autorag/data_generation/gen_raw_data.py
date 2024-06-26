#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os, re
import torch
from modelscope import AutoModelForCausalLM, AutoTokenizer  # pylint: disable=E0401
import jsonlines
from typing import List
import logging
from .prompt_dict import QUERYGENERATE_PROMPT
from transformers import GenerationConfig
from comps.dataprep.utils import document_loader

logging.basicConfig(
    format="%(asctime)s %(name)s:%(levelname)s:%(message)s",
    datefmt="%d-%M-%Y %H:%M:%S",
    level=logging.INFO
)

def document_filter(data_collection):
    documents = []
    for sample in data_collection:
        if len(data) < 5:
            continue
        documents.append(sample)
    return documents

def raw_data_generation(llm, input_path, file_json_path, generation_config):
    data_collections = []
    
    if isinstance(input_path, str):
       if os.path.isfile(input_path):
           data_collection = document_loader(input_path)
           data_collections.append(data_collection)
       elif os.path.isdir(input_path):
           for dirpath, dirnames, filenames in os.walk(input_path):
               for filename in filenames:
                   data_collection = document_loader(os.path.join(dirpath, filename))
                   data_collections.append(data_collection)
    else:
        print("Please check your upload file and try again!")
    documents = document_filter(data_collection)
    
    try:
        if isinstance(input, str):
            use_endpoint = False
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            llm = AutoModelForCausalLM.from_pretrained(model_id, device_map='auto', torch_dtype=torch.float16)
            model.eval()
        else:
            use_endpoint = True
            llm = llm
    except:
        print("Please check the setting llm!")

    for context in documents:
        if context:
            prompt = QUERYGENERATE_PROMPT.format(context=context)
            result = []
    
            for j in range(5):
                if not use_endpoint:
                    with torch.no_grad():
                        model_input = tokenizer(input, return_tensors="pt")
                        res = llm.generate(**model_input, generation_config=generation_config)[0]
                        res=tokenizer.decode(res, skip_special_tokens=True)
                else:
                    res = llm.invoke(prompt)
    
                res = res[res.find('Generated questions:') :]
                res = re.sub('Generated questions:', '', res)
                res = re.sub('---', '', res)
                res = res.split("?")[0:2]
                
                for content in res:
                    content = content.replace('1.', "").replace('2.', "")
                    content = content.replace('Evaluation:', "")
                    content = content.replace('#', " ").replace(r'\t', " ").replace('\n', ' ').replace('\n\n', ' ').strip()
                    content = content + '?'
                result.append(content)
    
            result_str=''
            result_set = list(set(result))
            for k in range(len(result_set)):
                result_str = result_str + str(k) + '. '+ result_set[k]
            
            if result_str and result_str.isspace()==False:
                data = {
                         "query": result_str,
                         "pos": [context],
                   }
                with jsonlines.open(file_json_path,"a") as file_json:
                      file_json.write(data)