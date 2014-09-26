import glob
import shutil
import os
import sys
import subprocess
import tarfile
import argparse
import vcf

import utils


class DestructWrapper(object):

    features = ['tumour_count', 'num_split', 'template_length_min', 'log_likelihood', 'log_cdf', 'mate_score']

    def __init__(self, install_directory):

        self.install_directory = install_directory

        self.ref_data_directory = os.path.join(self.install_directory, 'data')
        self.user_config_filename = os.path.join(self.install_directory, 'user_config.py')

        self.createref_script = os.path.join(os.path.dirname(__file__), os.path.pardir, 'createref.py')
        self.destruct_script = os.path.join(os.path.dirname(__file__), os.path.pardir, 'destruct.py')


    def install(self, **kwargs):

        Sentinal = utils.SentinalFactory(os.path.join(self.install_directory, 'sentinal_'), kwargs)

        with Sentinal('createref') as sentinal:

            if sentinal.unfinished:

                utils.makedirs(self.install_directory)
                
                with open(self.user_config_filename, 'w') as user_config_file:
                    if kwargs.get('chromosomes', None) is not None:
                        chromosomes = kwargs['chromosomes']
                        ensembl_assemblies = ['chromosome.'+a for a in chromosomes]
                        user_config_file.write('chromosomes = '+repr(chromosomes)+'\n')
                        user_config_file.write('ensembl_assemblies = '+repr(ensembl_assemblies)+'\n')

                createref_cmd = [sys.executable]
                createref_cmd += [self.createref_script]
                createref_cmd += [self.ref_data_directory]
                createref_cmd += ['-c', self.user_config_filename]

                subprocess.check_call(createref_cmd)


    def run(self, temp_directory, bam_filenames, output_filename):

        utils.makedirs(temp_directory)

        bam_list_filename = os.path.join(temp_directory, 'bam_list.tsv')

        with open(bam_list_filename, 'w') as bam_list_file:
            for lib_id, bam_filename in bam_filenames.iteritems():
                bam_list_file.write(lib_id + '\t' + bam_filename + '\n')

        breakpoints_filename = output_filename
        breakreads_filename = os.path.join(temp_directory, 'breakreads.tsv')
        plots_tar_filename = os.path.join(temp_directory, 'plots.tar')
        destruct_tmp_directory = os.path.join(temp_directory, 'tmp')

        destruct_cmd = list()
        destruct_cmd += [sys.executable]
        destruct_cmd += [self.destruct_script]
        destruct_cmd += [self.ref_data_directory]
        destruct_cmd += [bam_list_filename]
        destruct_cmd += [breakpoints_filename]
        destruct_cmd += [breakreads_filename]
        destruct_cmd += [plots_tar_filename]
        destruct_cmd += ['--config', self.user_config_filename]
        destruct_cmd += ['--tmp', destruct_tmp_directory]
        destruct_cmd += ['--nocleanup', '--repopulate', '--maxjobs', '4', '--loglevel', 'DEBUG']

        subprocess.check_call(destruct_cmd)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('install_directory', help='Destruct installation directory')
    parser.add_argument('--chromosomes', nargs='*', type=str, default=None, help='Reference chromosomes')
    args = parser.parse_args()

    delly = DestructWrapper(args.install_directory)

    delly.install(chromosomes=args.chromosomes)




