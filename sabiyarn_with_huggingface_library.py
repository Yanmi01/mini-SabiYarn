# -*- coding: utf-8 -*-
"""SabiYarn with Huggingface library

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1hGQhpyi3cPyO-Db1bBnUQ0xRWsGt5x1c
"""

!pip install -q datasets evaluate transformers[sentencepiece]
!pip install -q accelerate
!apt install -q git-lfs
!pip install -q torch matplotlib

!git config --global user.email "egbewaleyanmife@gmail.com"
!git config --global user.name "Yanmi01"

from huggingface_hub import notebook_login

notebook_login()

import os
import torch
from collections import defaultdict
from tqdm import tqdm

from datasets import load_dataset, DatasetDict, config
repo_name ="graelo/wikipedia"

config.HF_DATASETS_TRUST_REMOTE_CODE = True

hausa_dataset = load_dataset(repo_name, "20230901.ha", verification_mode="no_checks")
ibo_dataset = load_dataset(repo_name, "20230901.ig", verification_mode="no_checks")
yoruba_dataset = load_dataset(repo_name, "20230901.yo", verification_mode="no_checks")
eng_dataset = load_dataset(repo_name, "20230901.en", verification_mode="no_checks")

print(f"Hausa dataset: {hausa_dataset}")
print(f"Ibo dataset: {ibo_dataset}")
print(f"Yoruba dataset: {yoruba_dataset}")
print(f"English dataset: {eng_dataset}")

eng_dataset_sub = eng_dataset['train'].shuffle(seed=42).select(range(30000))
eng_dataset_sub

from datasets import concatenate_datasets

train_dataset = concatenate_datasets([
    hausa_dataset['train'],
    ibo_dataset['train'],
    yoruba_dataset['train'],
    eng_dataset_sub
])

batch_size = 2000
def get_training_corpus():
    return (
        train_dataset[i : i + batch_size]["text"]
        for i in range(0, len(train_dataset), batch_size)
    )


def get_training_corpus1():
    # train_dataset = dataset["train"]
    for start_idx in range(0, len(train_dataset), batch_size):
        samples = train_dataset[start_idx : start_idx + batch_size]
        yield samples["text"]

training_corpus = get_training_corpus1()

from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("bigscience/bloomz-560m")

new_tokenizer = tokenizer.train_new_from_iterator(training_corpus, 24576, new_special_tokens=["|end_of_text|"])

new_tokenizer.vocab_size

new_tokenizer.push_to_hub("Yanmife/mini-sabiyarn")

train_dataset

split_dataset = train_dataset.train_test_split(test_size=0.1, seed=2357, shuffle=True)
split_dataset['val'] = split_dataset.pop('test')

split_dataset

from transformers import AutoTokenizer

context_length = 256
tokenizer = AutoTokenizer.from_pretrained("Yanmife/mini-sabiyarn")

outputs = tokenizer(
    split_dataset["train"]["text"][:2],
    truncation=True,
    max_length=context_length,
    return_overflowing_tokens=True,
    return_length=True,
)

print(f"Input IDs length: {len(outputs['input_ids'])}")
print(f"Input chunk lengths: {(outputs['length'])}")
print(f"Chunk mapping: {outputs['overflow_to_sample_mapping']}")

def tokenize(element):
    outputs = tokenizer(
        element["text"],
        truncation=True,
        max_length=context_length,
        return_overflowing_tokens=True,
        return_length=True,
    )
    input_batch = []
    for length, input_ids in zip(outputs["length"], outputs["input_ids"]):
        if length == context_length:
            input_batch.append(input_ids)
    return {"input_ids": input_batch}


tokenized_datasets = split_dataset.map(
    tokenize, batched=True, remove_columns=split_dataset["train"].column_names
)
tokenized_datasets

from transformers import AutoTokenizer, GPT2LMHeadModel, AutoConfig

config = AutoConfig.from_pretrained(
    "gpt2",
    vocab_size=len(tokenizer),
    n_ctx=context_length,
    bos_token_id=tokenizer.bos_token_id,
    eos_token_id=tokenizer.eos_token_id,
)

model = GPT2LMHeadModel(config)
model_size = sum(t.numel() for t in model.parameters())
print(f"GPT-2 size: {model_size/1000**2:.1f}M parameters")

from transformers import DataCollatorForLanguageModeling

tokenizer.pad_token = tokenizer.eos_token
data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

out = data_collator([tokenized_datasets["train"][i] for i in range(5)])
for key in out:
    print(f"{key} shape: {out[key].shape}")

from transformers import Trainer, TrainingArguments

args = TrainingArguments(
    output_dir="mini-sabiyarn",
    per_device_train_batch_size=32,
    per_device_eval_batch_size=32,
    evaluation_strategy="steps",
    eval_steps=200,
    logging_steps=200,
    gradient_accumulation_steps=8,
    num_train_epochs=100,
    weight_decay=0.1,
    warmup_steps=1_000,
    lr_scheduler_type="cosine",
    learning_rate=5e-4,
    save_steps=200,
    fp16=True,
    push_to_hub=True,
    hub_strategy="every_save",
    hub_model_id="Yanmife/mini-sabiyarn",
)

trainer = Trainer(
    model=model,
    tokenizer=tokenizer,
    args=args,
    data_collator=data_collator,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["val"],
)

trainer.train(resume_from_checkpoint=True)

trainer.push_to_hub()