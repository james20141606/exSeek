#! /usr/bin/env python
from __future__ import print_function
import argparse, sys, os, errno
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')

from scipy import interp
from sklearn.metrics import roc_curve, roc_auc_score
from sklearn.preprocessing import RobustScaler
import numpy as np
import pandas as pd

command_handlers = {}
def command_handler(f):
    command_handlers[f.__name__] = f
    return f

def _compare_feature_selection_params(input_dir):
    from tqdm import tqdm
    import pandas as pd
    import matplotlib.pyplot as plt

    records = []
    pbar = tqdm(unit='directory')
    for compare_group in os.listdir(input_dir):
        for path in os.listdir(os.path.join(input_dir, compare_group)):
            classifier, n_features, selector, resample_method  = path.split('.')
            record = {
                'compare_group': compare_group,
                'classifier': classifier,
                'n_features': n_features,
                'selector': selector,
                'resample_method': resample_method
            }
            metrics = pd.read_table(os.path.join(input_dir, compare_group, path, 'metrics.{}.txt'.format(resample_method)))
            record['test_roc_auc_mean'] = metrics['test_roc_auc'].mean()
            if resample_method == 'leave_one_out':
                record['test_roc_auc_std'] = 0
            elif resample_method == 'stratified_shuffle_split':
                record['test_roc_auc_std'] = metrics['test_roc_auc'].std()
            pbar.update(1)
            records.append(record)
    pbar.close()
    records = pd.DataFrame.from_records(records)
    records.loc[:, 'n_features'] = records.loc[:, 'n_features'].astype('int')
    compare_groups = records.loc[:, 'compare_group'].unique()

    figsize = 3.5
    # Compare resample methods
    fig, axes = plt.subplots(1, len(compare_groups), 
                             figsize=(figsize*len(compare_groups), figsize),
                             sharey=True, sharex=False)
    for i, compare_group in enumerate(compare_groups):
        if len(compare_groups) > 1:
            ax = axes[i]
        else:
            ax = axes
        sub_df = records.query('compare_group == "{}"'.format(compare_group))
        pivot = sub_df.pivot_table(index=['classifier', 'n_features', 'selector'], 
                  columns=['resample_method'], 
                  values='test_roc_auc_mean')
        ax.scatter(pivot.loc[:, 'leave_one_out'], pivot.loc[:, 'stratified_shuffle_split'], s=12)
        ax.set_xlabel('AUROC (leave_one_out)')
        ax.set_ylabel('AUROC (stratified_shuffle_split)')
        ax.set_xlim(0.5, 1)
        ax.set_ylim(0.5, 1)
        ax.plot([0.5, 1], [0.5, 1], linestyle='dashed', color='gray', linewidth=0.8)
        ax.set_title(compare_group)

    # Compare classifiers
    fig, axes = plt.subplots(1, len(compare_groups), 
                             figsize=(figsize*len(compare_groups), figsize),
                             sharey=True, sharex=False)
    for i, compare_group in enumerate(compare_groups):
        if len(compare_groups) > 1:
            ax = axes[i]
        else:
            ax = axes
        sub_df = records.query('compare_group == "{}"'.format(compare_group))
        pivot = sub_df.pivot_table(index=['resample_method', 'n_features', 'selector'], 
                  columns=['classifier'], 
                  values='test_roc_auc_mean')
        ax.scatter(pivot.loc[:, 'logistic_regression'], pivot.loc[:, 'random_forest'], s=12)
        ax.set_xlabel('AUROC (logistic_regression)')
        ax.set_ylabel('AUROC (random_forest)')
        ax.set_xlim(0.5, 1)
        ax.set_ylim(0.5, 1)
        ax.plot([0.5, 1], [0.5, 1], linestyle='dashed', color='gray', linewidth=0.8)
        ax.set_title(compare_group)

    # Compare number of features
    fig, axes = plt.subplots(1, len(compare_groups), 
                             figsize=(figsize*len(compare_groups), figsize),
                             sharey=False, sharex=False)
    for i, compare_group in enumerate(compare_groups):
        if len(compare_groups) > 1:
            ax = axes[i]
        else:
            ax = axes
        sub_df = records.query('compare_group == "{}"'.format(compare_group))
        pivot = sub_df.pivot_table(index=['classifier', 'selector', 'resample_method'], 
                  columns=['n_features'], 
                  values='test_roc_auc_mean')
        ax.plot(np.repeat(pivot.columns.values.reshape((-1, 1)), pivot.shape[0], axis=1),
                pivot.values.T)
        ax.set_ylim(0.5, 1)
        ax.set_xlabel('Number of features')
        ax.set_ylabel('AUROC')
        ax.set_title(compare_group)

    # Compare feature selection methods
    fig, axes = plt.subplots(1, len(compare_groups), 
                             figsize=(figsize*len(compare_groups), figsize),
                             sharey=True, sharex=False)
    for i, compare_group in enumerate(compare_groups):
        if len(compare_groups) > 1:
            ax = axes[i]
        else:
            ax = axes
        sub_df = records.query('compare_group == "{}"'.format(compare_group))
        pivot = sub_df.pivot_table(index=['classifier', 'n_features', 'resample_method'], 
                  columns=['selector'], 
                  values='test_roc_auc_mean')
        ax.plot(np.repeat(pivot.columns.values.reshape((-1, 1)), pivot.shape[0], axis=1),
                pivot.values.T)
        ax.set_ylim(0.5, 1)
        ax.set_xlabel('Feature selection method')
        ax.set_ylabel('AUROC')
        ax.set_title(compare_group)
    return records

@command_handler
def compare_feature_selection_params(args):
    _compare_feature_selection_params(args.input_dir)
    logger.info('save plot: ' + args.output_file)
    plt.savefig(args.output_file)

def _compare_features(input_dir, datasets):
    import pandas as pd
    from tqdm import tqdm
    import seaborn as sns

    pbar = tqdm(unit='directory')
    records = []
    feature_matrices = {}
    #feature_support_matrices = {}
    feature_indicator_matrices = {}
    for dataset in datasets:
        cpm = pd.read_table('output/cpm_matrix/{}.txt'.format(dataset), index_col=0)
        for compare_group in os.listdir(os.path.join(input_dir, dataset)):
            feature_lists = {}
            #feature_supports = {}
            for path in os.listdir(os.path.join(input_dir, dataset, compare_group)):
                classifier, n_features, selector, resample_method  = path.split('.')
                if int(n_features) > 10:
                    continue
                if (classifier != 'random_forest') or (selector != 'robust'):
                    continue
                if resample_method != 'stratified_shuffle_split':
                    continue
                record = {
                    'compare_group': compare_group,
                    'classifier': classifier,
                    'n_features': n_features,
                    'selector': selector,
                    'resample_method': resample_method,
                    'dataset': dataset
                }
                # feature importance
                feature_lists[n_features] = pd.read_table(os.path.join(input_dir, dataset, compare_group,
                    path, 'feature_importances.txt'), header=None, index_col=0).iloc[:, 0]
                feature_lists[n_features].index = feature_lists[n_features].index.astype('str')
                # feature support
                #with h5py.File(os.path.join(input_dir, dataset, compare_group,
                #    path, 'evaluation.{}.h5'.format(resample_method)), 'r') as f:
                #    feature_support = np.mean(f['feature_selection'][:], axis=0)
                #    feature_support = pd.Series(feature_support, index=cpm.index.values)
                #    feature_support = feature_support[feature_lists[n_features].index.values]
                #    feature_supports[n_features] = feature_support
                # read metrics
                metrics = pd.read_table(os.path.join(input_dir, dataset, compare_group, 
                    path, 'metrics.{}.txt'.format(resample_method)))
                record['test_roc_auc_mean'] = metrics['test_roc_auc'].mean()
                if resample_method == 'leave_one_out':
                    record['test_roc_auc_std'] = 0
                elif resample_method == 'stratified_shuffle_split':
                    record['test_roc_auc_std'] = metrics['test_roc_auc'].std()
                pbar.update(1)
                records.append(record)
            # feature union set
            feature_set = reduce(np.union1d, [a.index.values for a in feature_lists.values()])
            # build feature importance matrix
            feature_matrix = pd.DataFrame(np.zeros((len(feature_set), len(feature_lists))),
                                          index=feature_set, columns=list(feature_lists.keys()))
            for n_features, feature_importance in feature_lists.items():
                feature_matrix.loc[feature_importance.index.values, n_features] = feature_importance.values
            feature_matrix.columns = feature_matrix.columns.astype('int')
            feature_matrix.index = feature_matrix.index.astype('str')
            feature_matrix = feature_matrix.loc[:, feature_matrix.columns.sort_values().values]
                    
            feature_matrices[(dataset, compare_group)] = feature_matrix
            # build feature indicator matrix
            feature_indicator_matrix = pd.DataFrame(np.zeros((len(feature_set), len(feature_lists))),
                                          index=feature_set, columns=list(feature_lists.keys()))
            for n_features, feature_importance in feature_lists.items():
                feature_indicator_matrix.loc[feature_importance.index.values, n_features] = 1
            feature_indicator_matrix.columns = feature_indicator_matrix.columns.astype('int')
            feature_indicator_matrix = feature_indicator_matrix.loc[:, feature_indicator_matrix.columns.sort_values().values]
            feature_indicator_matrices[(dataset, compare_group)] = feature_indicator_matrix
            
            if dataset in feature_fields:
                feature_meta = feature_matrix.index.to_series().str.split('|', expand=True)
                feature_meta.columns = feature_fields[dataset]
                if 'transcript_id' in feature_fields[dataset]:
                    feature_matrix.insert(
                        0, 'gene_type', 
                        transcript_table_by_transcript_id.loc[feature_meta['transcript_id'].values, 'gene_type'].values)
                    feature_matrix.insert(
                        0, 'gene_name', 
                        transcript_table_by_transcript_id.loc[feature_meta['transcript_id'].values, 'gene_name'].values)
                    
                elif 'gene_id' in feature_fields[dataset]:
                    feature_matrix.insert(
                        0, 'gene_type', 
                        transcript_table_by_gene_id.loc[feature_meta['gene_id'].values, 'gene_type'].values)
                    feature_matrix.insert(
                        0, 'gene_name', 
                        transcript_table_by_gene_id.loc[feature_meta['gene_id'].values, 'gene_name'].values)
                elif 'transcript_name' in feature_fields[dataset]:
                    feature_matrix.insert(
                        0, 'gene_type', 
                        transcript_table_by_transcript_name.loc[feature_meta['transcript_name'].values, 'gene_type'].values)
                    feature_matrix.insert(
                        0, 'gene_name', 
                        transcript_table_by_transcript_name.loc[feature_meta['transcript_name'].values, 'gene_name'].values)
                    
                feature_indicator_matrix.index = feature_matrix.loc[:, 'gene_name'].values + '|' + feature_matrix.loc[:, 'gene_type'].values
            # build feature support matrix
            #feature_support_matrix = pd.DataFrame(np.zeros((len(feature_set), len(feature_lists))),
            #                              index=feature_set, columns=list(feature_lists.keys()))
            #for n_features, feature_support in feature_supports.items():
            #    feature_support_matrix.loc[feature_support.index.values, n_features] = feature_support.values
            #feature_support_matrix.columns = feature_support_matrix.columns.astype('int')
            #feature_support_matrix = feature_matrix.loc[:, feature_support_matrix.columns.sort_values().values]
            #feature_support_matrices[(dataset, compare_group)] = feature_support_matrix
            fig, ax = plt.subplots(figsize=(6, 8))
            sns.heatmap(feature_indicator_matrix,
                        cmap=sns.light_palette('green', as_cmap=True), cbar=False, ax=ax, linewidth=1)
            ax.set_xlabel('Number of features')
            ax.set_ylabel('Fetures')
            ax.set_title('{}, {}'.format(dataset, compare_group))

            display(feature_matrix.style\
                .background_gradient(cmap=sns.light_palette('green', as_cmap=True))\
                .set_precision(2)\
                .set_caption('{}, {}'.format(dataset, compare_group)))

    pbar.close()
    metrics = pd.DataFrame.from_records(records)
    return metrics, feature_matrices, feature_indicator_matrices

def plot_roc_curve_ci(y, is_train, predicted_scores, ax, title=None):
    # ROC curve
    n_splits = is_train.shape[0]
    all_fprs = np.linspace(0, 1, 100)
    roc_curves = np.zeros((n_splits, len(all_fprs), 2))
    roc_aucs = np.zeros(n_splits)
    for i in range(n_splits):
        fpr, tpr, thresholds = roc_curve(y[~is_train[i]], predicted_scores[i, ~is_train[i]])
        roc_aucs[i] = roc_auc_score(y[~is_train[i]], predicted_scores[i, ~is_train[i]])
        roc_curves[i, :, 0] = all_fprs
        roc_curves[i, :, 1] = interp(all_fprs, fpr, tpr)
    roc_curves = pd.DataFrame(roc_curves.reshape((-1, 2)), columns=['fpr', 'tpr'])
    sns.lineplot(x='fpr', y='tpr', data=roc_curves, ci='sd', ax=ax,
                 label='Average ROAUC = {:.4f}'.format(roc_aucs.mean()))
    #ax.plot(fpr, tpr, label='ROAUC = {:.4f}'.format(roc_auc_score(y_test, y_score[:, 1])))
    #ax.plot([0, 1], [0, 1], linestyle='dashed')
    ax.set_xlabel('False positive rate')
    ax.set_ylabel('True positive rate')
    ax.plot([0, 1], [0, 1], linestyle='dashed', color='gray')
    if title:
        ax.set_title(title)
    ax.legend()

def _plot_10_features(input_dir, datasets, use_log=False, scale=False, title=None):
    pbar = tqdm_notebook(unit='directory')
    for dataset in datasets:
        sample_classes = pd.read_table('metadata/sample_classes.{}.txt'.format(groups[dataset]),
                                       header=None, index_col=0).iloc[:, 0]
        cpm = pd.read_table('output/cpm_matrix/{}.txt'.format(dataset), index_col=0)
        if use_log:
            cpm = np.log2(cpm + 0.001)
        if scale:
            X = RobustScaler().fit_transform(cpm.T.values).T
        X = cpm.values
        X = pd.DataFrame(X, index=cpm.index.values, columns=cpm.columns.values)
        for compare_group in os.listdir(os.path.join(input_dir, dataset)):
            for path in os.listdir(os.path.join(input_dir, dataset, compare_group)):
                classifier, n_features, selector, resample_method  = path.split('.')
                if int(n_features) != 10:
                    continue
                if (classifier != 'random_forest') or (selector != 'robust'):
                    continue
                if resample_method != 'stratified_shuffle_split':
                    continue
                record = {
                    'compare_group': compare_group,
                    'classifier': classifier,
                    'n_features': n_features,
                    'selector': selector,
                    'resample_method': resample_method,
                    'dataset': dataset
                }
                result_dir = os.path.join(input_dir, dataset, compare_group, path)
                with h5py.File(os.path.join(result_dir, 'evaluation.{}.h5'.format(resample_method))) as f:
                    train_index = f['train_index'][:]
                    predicted_scores = f['predictions'][:]
                    labels = f['labels'][:]
                fig, ax = plt.subplots(figsize=(8, 8))
                plot_roc_curve_ci(labels, train_index, predicted_scores, ax, 
                                  title='{}, {}'.format(dataset, compare_group))
                
                features = pd.read_table(os.path.join(result_dir, 'features.txt'), header=None).iloc[:, 0].values
                pbar.update(1)

    pbar.close()


def _evaluate_preprocess_methods(input_dirs, preprocess_methods, title=None):
    records = []
    pbar = tqdm_notebook(unit='directory')
    for preprocess_method, input_dir in zip(preprocess_methods, input_dirs):
        for compare_group in os.listdir(input_dir):
            for path in os.listdir(os.path.join(input_dir, compare_group)):
                classifier, n_features, selector, resample_method  = path.split('.')
                if int(n_features) > 50:
                    continue
                if (classifier != 'random_forest') or (selector != 'robust'):
                    continue
                if resample_method != 'stratified_shuffle_split':
                    continue
                record = {
                    'compare_group': compare_group,
                    'classifier': classifier,
                    'n_features': n_features,
                    'selector': selector,
                    'resample_method': resample_method,
                    'preprocess_method': preprocess_method
                }
                metrics = pd.read_table(os.path.join(input_dir, compare_group, path, 'metrics.{}.txt'.format(resample_method)))
                record['test_roc_auc_mean'] = metrics['test_roc_auc'].mean()
                if resample_method == 'leave_one_out':
                    record['test_roc_auc_std'] = 0
                elif resample_method == 'stratified_shuffle_split':
                    record['test_roc_auc_std'] = metrics['test_roc_auc'].std()
                pbar.update(1)
                records.append(record)
    pbar.close()
    records = pd.DataFrame.from_records(records)
    records['n_features'] = records.loc[:, 'n_features'].astype(np.int32)
    for compare_group, sub_df in records.groupby('compare_group'):
        pivot = sub_df.pivot_table(
            index='preprocess_method', columns='n_features', values='test_roc_auc_mean')
        #print(pivot.iloc[:, 0])
        #print(np.argsort(np.argsort(pivot.values, axis=0), axis=0)[:, 0])
        mean_ranks = np.mean(pivot.shape[0] - np.argsort(np.argsort(pivot.values, axis=0), axis=0), axis=1)
        mean_ranks = pd.Series(mean_ranks, index=pivot.index.values)
        mean_ranks = mean_ranks.sort_values()
        rename_index = ['{} (rank = {:.1f})'.format(name, value) for name, value in zip(mean_ranks.index, mean_ranks.values)]
        rename_index = pd.Series(rename_index, index=mean_ranks.index.values)
        sub_df = sub_df.copy()
        sub_df['preprocess_method'] = rename_index[sub_df['preprocess_method'].values].values
        sub_df['n_features'] = sub_df['n_features'].astype('int')
        sub_df = sub_df.sort_values(['preprocess_method', 'n_features'], ascending=True)
        sub_df['n_features'] = sub_df['n_features'].astype('str')
        fig, ax = plt.subplots(figsize=(8, 8))                      
        #sns.lineplot('n_features', 'test_roc_auc_mean', hue='preprocess_method', data=sub_df, 
        #          ci=None, ax=ax, markers='o', hue_order=rename_index.values, sort=False)
        for preprocess_method in rename_index.values:
            tmp_df = sub_df[sub_df['preprocess_method'] == preprocess_method]
            ax.plot(np.arange(tmp_df.shape[0]) + 1, tmp_df['test_roc_auc_mean'], label=preprocess_method)
            ax.set_xticks(np.arange(tmp_df.shape[0]) + 1)
            ax.set_xticklabels(tmp_df['n_features'])
        ax.set_xlabel('Number of features')
        ax.set_ylabel('Average AUROC')
        if len(preprocess_methods) > 1:
            ax.legend(title='Preprocess method', bbox_to_anchor=(1.04,0.5), 
                      loc="center left", borderaxespad=0)
        ax.set_ylim(0.5, 1)
        if title:
            ax.set_title(title + ', ' + compare_group)

@command_handler
def evaluate_preprocessing_methods(args):
    _evaluate_preprocess_methods(args.input_dirs, args.precessing_methods)

@command_handler
def fastqc_summary(args):
    from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
    
    fastqc_dir = os.path.join(args.input_dir)
    logger.info('read fastq directory: ' + args.input_dir)
    
if __name__ == '__main__':
    main_parser = argparse.ArgumentParser(description='Preprocessing module')
    subparsers = main_parser.add_subparsers(dest='command')

    parser = subparsers.add_parser('fastqc_summary', 
        help='create an HTML summary report for fastqc result')
    parser.add_argument('--input-dir', '-i', type=str, required=True,
        help='output directory of fastqc')
    parser.add_argument('--output-prefix', '-o', type=str, default='-',
        help='prefix of output files')
    
    args = main_parser.parse_args()
    if not args.command:
        main_parser.print_help()
        sys.exit(1)
    logger = logging.getLogger('report.' + args.command)

    command_handlers.get(args.command)(args)