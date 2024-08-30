#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 27 15:00:47 2023

@author: simon kern
"""
import os
import random
import warnings
from itertools import product, permutations, groupby
import pandas as pd
import numpy as np
from tqdm import tqdm
from scipy.stats import poisson, kstest
from scipy.stats import expon

#%%

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def de_bruijn_k2(items, allow_repetitions=False):
    """
    finds the debruijn-sequence for a given alphabet with each transition
    X->Y being present exactly once

    :param items: any iterable
    :param allow_repetitions: Allow self-transition i.e. A->A
    """
    if isinstance(items, int): items = np.arange(1, items+1)
    atoms = set(items)

    max_tries = 1000
    tries = 0
    while tries<max_tries:
        try:
            transitions = {x:[y for y in atoms if (not y==x) or allow_repetitions] for x in atoms}
            seq1 = np.random.choice(list(transitions))
            sequence = []
            while len(transitions)>0:
                seq2 = np.random.choice(transitions[seq1])
                sequence.append(seq2)
                transitions[seq1].remove(seq2)
                if len(transitions[seq1])==0:
                    transitions.pop(seq1)
                seq1=seq2
        except:
            tries+=1
            continue
        sequence_str = [str(x) for x in sequence]
        _, counts = np.unique(sequence, return_counts=True)
        assert len(set(counts))==1, f'ERROR, unequal number of items {counts}'
        return sequence_str
    raise Exception(f'did not find debruijn-sequence after {tries} tries')


def place_distractors(items, proba=0.2):
    """given a list of items places the distractor positions such that
    each item is equally often a distractor"""
    items = np.array(items)
    uniques, counts = np.unique(items, return_counts=True)
    assert np.std(counts)==0, 'not all items are equally often'
    per_item = np.round(counts[0]*proba)
    if (per_item * 1/proba)!=counts[0]:
        warnings.warn(f'Cant make probability exactly {proba}, is now {per_item/counts[0]}')

    is_distractor = np.zeros(len(items))
    p = np.array([1/len(items)]*len(items))
    idx = np.arange(len(items))

    for item in uniques:
        idx_sub = idx[items==item]
        p_sub = p[items==item]
        assert len(idx_sub)==counts[0]  # sanity check
        i = np.random.choice(idx_sub, p=p_sub/p_sub.sum())
        is_distractor[i] = True

        # now normalize p vector such that neighbouring items are less likely
        p[i] = 0
        if i>0:
            p[i-1] **= 3
        if i<len(p)-1:
            p[i+1] **= 3

    assert sum(is_distractor)==(len(uniques)*per_item)
    return is_distractor.astype(int)

def distribute_sequences(all_sequences, seq_per_subj):
    """return the sequences such that they are distributed across participants
    
    make sure that they are 
    """
    assert len(all_sequences)%seq_per_subj==0
    n_subj = len(all_sequences) // seq_per_subj

    transitions_base = {''.join(x):0 for x in list(permutations('ABCDE', 2))}

    best_std = np.inf
    best_distribution = all_sequences.copy()

    for _ in tqdm(list(range(100000)), desc='optimizing distribution'):
        np.random.shuffle(all_sequences)
        stds = []
        for seqs in chunks(all_sequences, seq_per_subj):
            transitions = transitions_base.copy()
            # assert len(seqs)==8  # sanity check
            for seq in seqs:
                for trans in [seq[i:i+2] for i in range(4)]:
                    transitions[trans] += 1

            values = list(transitions.values())
            std = np.var(values)
            stds.append(std)

        if (new_best_std:=np.std(stds))<best_std:
            best_std = new_best_std
            best_distribution = all_sequences.copy()
            # print(f'new best: {new_best_std}')

    sequences_subjects = []
    for i in tqdm(list(range(n_subj)), desc='distribution within subject'):
        seq_sub = best_distribution[i*seq_per_subj:i*seq_per_subj+seq_per_subj]


        min_overlap = 4*len(seq_sub)
        min_overlap_seq_sub = seq_sub.copy()

        for seq_sub_perm in permutations(seq_sub):
            trans1 = set()
            trans2 = set()
            for seq in seq_sub_perm[:len(seq_sub_perm)//2]:
                for trans in [seq[i:i+2] for i in range(len(seq)-1)]:
                    trans1.add(trans)

            for seq in seq_sub_perm[len(seq_sub_perm)//2:]:
                for trans in [seq[i:i+2] for i in range(len(seq)-1)]:
                    trans2.add(trans)
            if (curr_ov:=len(trans1.intersection(trans2)))<min_overlap:
                min_overlap = curr_ov
                min_overlap_seq_sub = seq_sub_perm

        seq_subj_unique = [[x, speeds[i//2]] for i, x in enumerate(min_overlap_seq_sub)]
        sequences_subjects.append(seq_subj_unique)

    return sequences_subjects


def choose_cue(sequence):
    """use poisson distribution to choose target of this sequence

    The serial position of the target for each trial was randomly drawn from a
    Poisson distribution with λ = 1.9 and truncated to an interval from 1 to 5.
    Thus, across all trials, the targets appeared more often at the later
    compared to earlier positions of the sequence. This was done to reduce the
    likelihood that participants stopped to process stimuli or diverted their
    attention after they identified the position of the target object. The
    serial position of the alternative response option was drawn from the same
    distribution as the serial position of the target.

    returns: target_name, target_idx, lure_idx
    """

    # The serial idx of the target for each trial was randomly drawn from a
    # Poisson distr. with λ = 1.9 and truncated to an interval from 1 to 5.
    draw_poisson = poisson.pmf(np.arange(len(sequence)) + 1, 1.9)
    p = draw_poisson / draw_poisson.sum()

    # not mentioned in the paper, but obviously the poisson needs to be inverse
    idxs = np.arange(len(sequence))[::-1]
    target_idx = np.random.choice(idxs, p=p)
    target_name = os.path.splitext(os.path.basename(sequence[target_idx]))[0]

    # draw the lure from the same distribution until but avoid duplicates
    while (lure_idx:=np.random.choice(idxs, p=p))==target_idx:pass
    assert lure_idx!=target_idx  # never trust your own code ;-)

    return target_name, target_idx, lure_idx


#%%
np.random.seed(0)
random.seed(0)
n_blocks = 12
seq_per_subj = 8
n_subj = 40
speeds = [32, 64, 128, 512]

max_reward = 500  # maximum reward to obtain in cents

images = [x for x in os.listdir('./stimuli') if not 'flag' in x]

stimuli = {chr(65+i):f'./stimuli/{file}' for i, file  in enumerate(images)}
items = 'ABCDE'

localizer_seq = [de_bruijn_k2(items, allow_repetitions=True) for _ in range(n_subj*n_blocks)]

all_sequences = [''.join(x) for x in list(permutations(items))]
np.random.shuffle(all_sequences)  # shake once for randomness
sequences_subjects = distribute_sequences(all_sequences, seq_per_subj=8)

#%%
# check all debruijn sequences are unique. Very unlikely to have duplicates
assert len(set([''.join(seq) for seq in localizer_seq]))==n_subj*n_blocks

for subj in range(n_subj):
    localizer_file = f'./sequences/localizer_{subj}.csv'
    sequences_file = f'./sequences/sequences_{subj}.csv'
    df_localizer = pd.DataFrame()
    df_sequences = pd.DataFrame()
    
    t_blocks = []

    for block in range(n_blocks):

        # localizer trials
        localizer = localizer_seq[(subj*n_blocks)+block]
        localizer_img = [stimuli[x] for x in localizer]

        isi_loc = expon.rvs(scale=1.5, size=len(localizer_img))+1
        # truncate over 10 to not have extremely long timings
        # isi_loc = np.clip(isi_loc, None, 10)
    
        df_localizer_block = pd.DataFrame()
        df_localizer_block['block'] = [block] * len(localizer_img)
        df_localizer_block['trial'] = np.arange(len(localizer_img))
        df_localizer_block['img']= localizer_img
        df_localizer_block['isi']= isi_loc
        df_localizer_block['distractor'] = place_distractors(localizer_img)

        df_localizer = pd.concat([df_localizer, df_localizer_block], ignore_index=True)

        # sequence trials
        # warnings.warn('check this assignment below')
        seq_block = np.random.permutation(sequences_subjects[subj% (len(all_sequences) // seq_per_subj)])
        sequences_subj = [x[0] for x in seq_block]
        timings_subj = [x[1] for x in seq_block]
        sequences_img = [[stimuli[img] for img in x] for x in sequences_subj]
        df_sequences_block = pd.DataFrame()
        df_sequences_block['block'] = [block]*len(sequences_img)
        df_sequences_block['trial'] = np.arange(len(sequences_img))
        df_sequences_block['isi']  = timings_subj

        df_tmp = pd.DataFrame({f'img{i}':[sequences_img[x][i] for x in range(len(sequences_img))]
                 for i in range(5)})
        choices = [choose_cue(sequence) for sequence in sequences_img]
        positions = ['r']*(len(choices)//2) + ['l']*(len(choices)//2)
        np.random.shuffle(positions)
        df_tmp['cue'] = [x[0] for x in choices]
        df_tmp['target_idx'] = [x[1] for x in choices]
        df_tmp['lure_idx'] = [x[2] for x in choices]
        df_tmp['correct_pos'] = positions

        df_sequences_block = pd.concat([df_sequences_block, df_tmp],  axis=1)

        df_sequences = pd.concat([df_sequences, df_sequences_block], ignore_index=True)

        # manual overwrite for dummy trials
        if subj==0 and block==0:
            df_localizer.loc[:, 'distractor'] = 0
            df_localizer.loc[1, 'distractor'] = 1
            df_localizer.loc[3, 'distractor'] = 1
            df_localizer.loc[5, 'img'] = './stimuli/Katze.jpg'
            df_localizer.loc[6, 'img'] = './stimuli/Katze.jpg'
            
            df_sequences.loc[0, 'isi'] = 128
            df_sequences.loc[1, 'isi'] = 256
            df_sequences.loc[2, 'isi'] = 64   
            
            
        t_block = df_localizer_block.isi.sum() + (0.3+0.5)*len(df_localizer_block)  
        t_block += 12*len(df_sequences_block) + (1+1.5+0.25+2.5)*len(df_sequences_block)

        t_blocks += [t_block]
   
    # estimate experiment runtime
    # sum all ISI of the localizer plus fixation cross and image
    exp_time_loc = df_localizer.isi.sum() +(0.3+0.5)*len(df_localizer)  
    # each sequence showing is 10 sec including buffer
    exp_time_seq = 10*len(df_sequences) + (1+1.5+0.25+2.5) * len(df_sequences)
    exp_time = exp_time_seq + exp_time_loc
            
    df_localizer.to_csv(localizer_file)
    df_sequences.to_csv(sequences_file)
    print(f'{subj} runtime: {exp_time/60:.1f} min | localizer ~{exp_time_loc/60:.1f} min + sequences {exp_time_seq/60:.1f} min')
    
    # sanity checks
    assert max([len(x) for x in groupby(df_localizer.img)])<=2
    assert len(set([len(np.unique([x for x in r if '/' in str(x)])) for _, r in df_sequences.iterrows()]))==1

    
n_distractors = sum(df_localizer.distractor)
n_sequences = len(df_sequences)
n_reward = int(np.round(max_reward/(n_sequences+n_distractors)))
print(f'\n\n{n_sequences} sequence trials')
print(f'{n_distractors} distractor trials')
print(f'reward_per_trial = {n_reward} ct')
with open('reward_in_ct.txt', 'w') as f:
    f.write(str(n_reward))
    