#!/bin/bash

################## Train arguments ###############
# Train epoch
epoch=100
# Learning rate
lr=0.0001
# Weight decay
weight_decay=0.0005
# Batch size for train
batch_size=8
# momentum
momentum=0.9
#############################

# Path to Images
ImagePath="data/PISC/image"
# Path to object boxes
ObjectsPath="data/objects/PISC_objects/"
# Path to test list
TrainList="data/list/PISC_fine_level_train.txt"
# Path to test list
TestList="data/list/PISC_fine_level_test.txt"
# Number of classes
num=6
# Path to save scores
ResultPath="experiments/logs/train_first_glance"

# Path to model
ModelPath="models/First_Glance_fine_model.pth.tar"

python ./tools/train_first_glance.py \
    $ImagePath \
    $ObjectsPath \
    $TrainList \
    $TestList \
    --weights $ModelPath \
    -n $num \
    -b $batch_size \
    --lr $lr \
    -m $momentum \
    --wd $weight_decay \
    --e $epoch \
    --print-freq 100 \
    --write-out --result-path $ResultPath
