
import collections
import pandas as pd
import numpy as np
import scipy
import scipy.stats

import utils.misc


breakpoint_fields = ['cluster_id', 'prediction_id',
                     'chromosome_1', 'strand_1', 'position_1',
                     'chromosome_2', 'strand_2', 'position_2',
                     'count', 'inserted']


realignment_fields = ['cluster_id', 'prediction_id', 'cluster_end',
                      'library_id', 'read_id', 'read_end', 'align_id',
                      'aligned_length', 'template_length', 'score']


score_stats_fields = ['aligned_length', 'expon_lda']


likelihoods_fields = ['cluster_id', 'prediction_id',
                      'library_id', 'read_id',
                      'read_end_1', 'read_end_2',
                      'aligned_length_1', 'aligned_length_2',
                      'template_length_1', 'template_length_2',
                      'score_1', 'score_2',
                      'score_log_likelihood_1', 'score_log_likelihood_2',
                      'score_log_cdf_1', 'score_log_cdf_2',
                      'inslen', 'template_length', 'length_z_score',
                      'length_log_likelihood', 'length_log_cdf',
                      'log_likelihood', 'log_cdf']


def predict_breaks(clusters_filename, spanning_filename, split_filename, breakpoints_filename):

    # Read all clusters
    fields = ['cluster_id', 'cluster_end', 'lib_id', 'read_id', 'read_end', 'align_id']
    clusters = pd.read_csv(clusters_filename, sep='\t', names=fields)

    reads = clusters[['lib_id', 'read_id']].drop_duplicates()

    def read_filter(df):
        return df.merge(reads, on=['lib_id', 'read_id'], how='inner')

    # Read only spanning reads relevant clusters
    fields = ['lib_id', 'read_id', 'read_end', 'align_id', 'chromosome', 'strand', 'start', 'end', 'score']
    csv_iter = pd.read_csv(spanning_filename, sep='\t', iterator=True, chunksize=1000,
                                              names=fields, converters={'chromosome':str})
    spanning = pd.concat([read_filter(chunk) for chunk in csv_iter])

    span_index_cols = ['lib_id', 'read_id', 'read_end', 'align_id']

    spanning.set_index(span_index_cols, inplace=True)

    # Read only split reads relevant clusters
    fields = ['lib_id', 'read_id', 'read_end',
              'align_id_1', 'chromosome_1', 'strand_1', 'position_1',
              'align_id_2', 'chromosome_2', 'strand_2', 'position_2',
              'inserted', 'score']
    csv_iter = pd.read_csv(split_filename, sep='\t', iterator=True, chunksize=1000,
                                           names=fields, converters={'chromosome':str},
                                           na_values=['.'])
    split = pd.concat([read_filter(chunk) for chunk in csv_iter])

    split_index_cols = ['lib_id', 'read_id', 'align_id_1', 'align_id_2']

    split.set_index(split_index_cols, inplace=True)

    split['inserted'] = split['inserted'].fillna('')

    def flip_split_positions(row):
        if row['flip']:
            row['chromosome_1'], row['chromosome_2'] = row['chromosome_2'], row['chromosome_1']

    predictions = list()

    for cluster_id, cluster_rows in clusters.groupby('cluster_id'):
        
        prediction_id = 0
        
        # Create a table of spanning alignments for this cluster
        cluster_spanning = spanning.merge(cluster_rows, left_index=True, right_on=span_index_cols)
        
        # Predict based on spanning reads
        span_predict_agg = {'chromosome':max, 'strand':max, 'start':min, 'end':max}
        pred = cluster_spanning.groupby('cluster_end').agg(span_predict_agg).reset_index()
        pred['position'] = np.where(pred['strand'] == '+', pred['end'], pred['start'])
        pred = pred.drop(['start', 'end'], axis=1)
        
        # Reformat table
        pred['cluster_id'] = cluster_id
        pred['prediction_id'] = prediction_id
        pred = pred.set_index(['cluster_id', 'prediction_id', 'cluster_end']).unstack()
        pred.columns = [a+'_'+str(b+1) for a, b in pred.columns.values]
        pred.reset_index(inplace=True)
        pred['count'] = 0
        pred['inserted'] = ''
        
        # Add spanning read prediction
        predictions.append(pred)
        prediction_id += 1
        
        paired = cluster_rows.set_index(['lib_id', 'read_id', 'read_end'])[['cluster_end', 'align_id']].unstack()
        paired.columns = ['cluster_end_1', 'cluster_end_2', 'align_id_1', 'align_id_2']
        
        paired['flip'] = paired['cluster_end_1'] != 0
        paired = paired.drop(['cluster_end_1', 'cluster_end_2'], axis=1)
        paired = paired.reset_index()
        
        cluster_split = split.merge(paired, left_index=True, right_on=split_index_cols)
        
        if len(cluster_split.index) == 0:
            continue
            
        cluster_split.loc[cluster_split['flip'], 'chromosome_1'], cluster_split.loc[cluster_split['flip'], 'chromosome_2'] = \
            cluster_split.loc[cluster_split['flip'], 'chromosome_2'], cluster_split.loc[cluster_split['flip'], 'chromosome_1']
        
        cluster_split.loc[cluster_split['flip'], 'strand_1'], cluster_split.loc[cluster_split['flip'], 'strand_2'] = \
            cluster_split.loc[cluster_split['flip'], 'strand_2'], cluster_split.loc[cluster_split['flip'], 'strand_1']
        
        cluster_split.loc[cluster_split['flip'], 'position_1'], cluster_split.loc[cluster_split['flip'], 'position_2'] = \
            cluster_split.loc[cluster_split['flip'], 'position_2'], cluster_split.loc[cluster_split['flip'], 'position_1']
        
        cluster_split['seed_end'] = np.where(cluster_split['flip'], 1-cluster_split['read_end'], cluster_split['read_end'])
        
        def revcomp_inserted(row):
            if row['seed_end'] == 0:
                return row['inserted']
            else:
                return utils.misc.reverse_complement(row['inserted'])
        
        cluster_split['inserted'] = cluster_split.apply(revcomp_inserted, axis=1)
        
        cluster_split['inslen'] = cluster_split['inserted'].apply(len)
        
        cluster_split.set_index(['position_1', 'position_2', 'inslen'], inplace=True)
        cluster_split = cluster_split.sort_index()
        
        # Calculate highest scoring split
        split_score_sums = cluster_split.groupby(level=[0, 1, 2])['score'].sum()
        split_score_sums.sort(ascending=False)
        
        # Select split alignments for highest scoring split
        highscoring = cluster_split.loc[split_score_sums.index[0]:split_score_sums.index[0]].reset_index()
        
        # Consensus for inserted sequence
        inserted = np.array([np.array(list(a)) for a in highscoring['inserted'].values])
        consensus = list()
        for nt_list in inserted.T:
            consensus.append(collections.Counter(nt_list).most_common(1)[0][0])
        consensus = ''.join(consensus)

        # Reformat table
        pred = highscoring.iloc[0:1].copy()
        pred['cluster_id'] = cluster_id
        pred['prediction_id'] = prediction_id
        pred['count'] = len(highscoring.index)
        pred['inserted'] = consensus
        pred = pred[breakpoint_fields]
        
        predictions.append(pred)
        prediction_id += 1

    if len(predictions) == 0:
        with open(breakpoints_filename, 'w'):
            pass
        return
        
    predictions = pd.concat(predictions, ignore_index=True)

    predictions.loc[predictions['inserted'] == '', 'inserted'] = '.'

    predictions = predictions[breakpoint_fields]
    predictions.to_csv(breakpoints_filename, sep='\t', index=False, header=False)


def calculate_cluster_weights(breakpoints_filename, weights_filename):
    
    epsilon = 0.0001
    itx_distance = 1000000000
    
    breakpoints = pd.read_csv(breakpoints_filename, sep='\t')

    breakpoints['distance'] = np.absolute(breakpoints['position_1'] - breakpoints['position_2'])
    breakpoints.loc[breakpoints['chromosome_1'] != breakpoints['chromosome_2'], 'distance'] = itx_distance
    breakpoints['weight'] = 1.0 + epsilon * np.log(breakpoints['distance'])

    breakpoints = breakpoints.sort('cluster_id')
    breakpoints[['cluster_id', 'weight']].to_csv(weights_filename, sep='\t', index=False, header=False)


def calculate_realignment_likelihoods(breakpoints_filename, realignments_filename, score_stats_filename,
                                      likelihoods_filename, match_score, fragment_mean, fragment_stddev):

    match_score = float(match_score)
    fragment_mean = float(fragment_mean)
    fragment_stddev = float(fragment_stddev)

    score_stats = pd.read_csv(score_stats_filename, sep='\t', names=score_stats_fields)

    breakpoints = pd.read_csv(breakpoints_filename, sep='\t', names=breakpoint_fields,
                              converters={'chromosome_1':str, 'chromosome_2':str},
                              na_values=['.'])

    breakpoints['inserted'] = breakpoints['inserted'].fillna('')

    breakpoints['inslen'] = breakpoints['inserted'].apply(len)

    data = pd.read_csv(realignments_filename, sep='\t', names=realignment_fields)

    assert data.duplicated(subset=['cluster_id', 'prediction_id', 'library_id', 'read_id', 'read_end']).sum() == 0

    data = data.merge(score_stats, on='aligned_length')

    # Alignment score likelihood and CDF
    data['max_score'] = match_score * data['aligned_length']
    data['score_diff'] = data['max_score'] - data['score']
    data['score_log_likelihood'] = np.log(data['expon_lda']) - \
                                          data['expon_lda'] * data['score_diff']
    data['score_log_cdf'] = -data['expon_lda'] * data['score_diff']

    # Unstack on cluster end
    index_fields = ['cluster_id', 'prediction_id', 'library_id', 'read_id']
    unstack_field = ['cluster_end']
    data_fields = ['read_end', 'aligned_length', 'template_length',
                   'score', 'score_log_likelihood', 'score_log_cdf']
    data = data.set_index(index_fields + unstack_field)[data_fields].unstack()
    data.columns = ['_'.join((a, str(b+1))) for a, b in data.columns.values]
    data.reset_index(inplace=True)

    # Merge insert length from breakpoint predictions
    data = data.merge(breakpoints[['cluster_id', 'prediction_id', 'inslen']],
                      on=['cluster_id', 'prediction_id'])

    data['template_length'] = data['template_length_1'] + data['template_length_2'] + data['inslen']

    # Template length likelihood and CDF
    constant = 1. / ((2 * np.pi)**0.5 * fragment_stddev)
    data['length_z_score'] = (data['template_length'] - fragment_mean) / fragment_stddev
    data['length_log_likelihood'] = -np.log(constant) - np.square(data['length_z_score']) / 2.
    data['length_log_cdf'] = np.log(2. * scipy.stats.norm.sf(data['length_z_score'].abs()))

    data['log_likelihood'] = data['score_log_likelihood_1'] + \
                             data['score_log_likelihood_2'] + \
                             data['length_log_likelihood']
    data['log_cdf'] = data['score_log_cdf_1'] + \
                      data['score_log_cdf_2'] + \
                      data['length_log_cdf']

    data = data.reset_index()

    data = data[likelihoods_fields]

    data.to_csv(likelihoods_filename, sep='\t', index=False, header=False)


def read_merge_write(in_filename, in_names, to_merge, merge_cols, out_filename):
    csv_iter = pd.read_csv(in_filename, sep='\t', names=in_names,
                           iterator=True, chunksize=1000)
    first = True
    for chunk in csv_iter:
        chunk = chunk.merge(to_merge, left_on=merge_cols,
                            right_index=True, how='inner')
        chunk.to_csv(out_filename, sep='\t', mode=('a', 'w')[first], index=False, header=first)
        first = False


def select_predictions(breakpoints_filename, selected_breakpoints_filename,
                       likelihoods_filename, selected_likelihoods_filename):

    likelihoods = pd.read_csv(likelihoods_filename, sep='\t', names=likelihoods_fields,
                          usecols=['cluster_id', 'prediction_id', 'log_likelihood'])

    selected = likelihoods.set_index(['cluster_id', 'prediction_id'])\
                          .groupby(level=[0])['log_likelihood']\
                          .idxmax()
    selected = pd.DataFrame(list(selected.values), columns=['cluster_id', 'prediction_id'])

    selected.set_index(['cluster_id', 'prediction_id'], inplace=True)

    read_merge_write(likelihoods_filename, likelihoods_fields, selected,
                     ['cluster_id', 'prediction_id'],
                     selected_likelihoods_filename)

    read_merge_write(breakpoints_filename, breakpoint_fields, selected,
                     ['cluster_id', 'prediction_id'],
                     selected_breakpoints_filename)



