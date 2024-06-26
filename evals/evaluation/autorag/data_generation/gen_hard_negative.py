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

import json
import random

import faiss
import jsonlines
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def create_index(embeddings):
    index = faiss.IndexFlatIP(len(embeddings[0]))
    embeddings = np.asarray(embeddings, dtype=np.float32)
    index.add(embeddings)
    return index


def batch_search(index, query, topk: int = 200, batch_size: int = 64):
    all_scores, all_inxs = [], []
    for start_index in tqdm(range(0, len(query), batch_size), desc="Batches", disable=len(query) < 256):
        batch_query = query[start_index : start_index + batch_size]
        batch_scores, batch_inxs = index.search(np.asarray(batch_query, dtype=np.float32), k=topk)
        all_scores.extend(batch_scores.tolist())
        all_inxs.extend(batch_inxs.tolist())
    return all_scores, all_inxs


def get_corpus(candidate_pool):
    corpus = []
    for line in open(candidate_pool):
        line = json.loads(line.strip())
        corpus.append(line["text"])
    return corpus


def find_knn_neg(embedder, input_file, candidate_pool, output_file, sample_range, negative_number):
    corpus = []
    queries = []
    train_data = []
    for line in open(input_file):
        line = json.loads(line.strip())
        train_data.append(line)
        corpus.extend(line["pos"])
        if "neg" in line:
            corpus.extend(line["neg"])
        queries.append(line["query"])

    if candidate_pool is not None:
        if not isinstance(candidate_pool, list):
            candidate_pool = get_corpus(candidate_pool)
        corpus = list(set(candidate_pool))
    else:
        corpus = list(set(corpus))

    p_vecs = embedder.embed_documents(corpus)
    q_vecs = embedder.embed_documents(queries)

    index = create_index(p_vecs)
    _, all_inxs = batch_search(index, q_vecs, topk=sample_range[-1])
    assert len(all_inxs) == len(train_data)

    for i, data in enumerate(train_data):
        query = data["query"]
        inxs = all_inxs[i][sample_range[0] : sample_range[1]]
        filtered_inx = []
        for inx in inxs:
            if inx == -1:
                break
            if corpus[inx] not in data["pos"] and corpus[inx] != query:
                filtered_inx.append(inx)

        if len(filtered_inx) > negative_number:
            filtered_inx = random.sample(filtered_inx, negative_number)
        data["neg"] = [corpus[inx] for inx in filtered_inx]

    with open(output_file, "w") as f:
        for data in train_data:
            if len(data["neg"]) < negative_number:
                data["neg"].extend(random.sample(corpus, negative_number - len(data["neg"])))
            f.write(json.dumps(data, ensure_ascii=False) + "\n")


def mine_hard_negatives(embedder, input_file, output_file, range_for_sampling, negative_number):
    candidate_pool = None
    sample_range = range_for_sampling.split("-")
    sample_range = [int(x) for x in sample_range]

    find_knn_neg(
        embedder,
        input_file=input_file,
        candidate_pool=candidate_pool,
        output_file=output_file,
        sample_range=sample_range,
        negative_number=negative_number,
    )