"""===========================
Pipeline template
===========================

.. Replace the documentation below with your own description of the
   pipeline's purpose

Overview
========

This pipeline computes the word frequencies in the configuration
files :file:``pipeline.ini` and :file:`conf.py`.

Usage
=====

See :ref:`PipelineSettingUp` and :ref:`PipelineRunning` on general
information how to use CGAT pipelines.

Configuration
-------------

The pipeline requires a configured :file:`pipeline.ini` file.
CGATReport report requires a :file:`conf.py` and optionally a
:file:`cgatreport.ini` file (see :ref:`PipelineReporting`).

Default configuration files can be generated by executing:

   python <srcdir>/pipeline_@template@.py config

Input files
-----------

None required except the pipeline configuration files.

Requirements
------------

The pipeline requires the results from
:doc:`pipeline_annotations`. Set the configuration variable
:py:data:`annotations_database` and :py:data:`annotations_dir`.

Pipeline output
===============

.. Describe output files of the pipeline here

Glossary
========

.. glossary::


Code
====

"""
from ruffus import *
import sys
import os
import CGAT.Experiment as E
import CGATPipelines.Pipeline as P

# load options from the config file
PARAMS = P.getParameters(
    ["%s/pipeline.ini" % os.path.splitext(__file__)[0],
     "../pipeline.ini",
     "pipeline.ini"])


# ---------------------------------------------------
# Specific pipeline tasks
    
''' below, use this to change environemtn before calling tool/script
need to change env name from py36 to desired one'''
   
# PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/py36-v1/bin
# CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/py36-v1

    
###### need to decide if I start with demultiplexed from iCount
###### or perform some custom demultiplexing with help of umi_tools

''' If I am to demultiplex using iCount:
'''

# Cutadapt

@transform('*NN.fastq.gz', regex(r'demux_NNN(.*)NN.fastq.gz'), r'\1.trim.fastq.gz') 
def cutadapt(infile, outfile):
    ''' trims 3' adapter and removes low quality reads '''
    statement = ''' cutadapt -q %(cutadapt_minphred)s --m %(cutadapt_minlength) -a %(general_adapter)s
    -o %(outfile)s %(infile)s
    '''
    P.run()

@transform(cutadapt, regex(r'(\S+).trim.fastq.gz'), r'mappedreps/\1.rep.bam')
def STARrmRep(infile, outfile):
    ''' maps to repetitive elements, produces 2 files:
        mapped - file1.name; unmapped file2.name '''
    outprefix = P.snip(outfile, ".bam")
    statement = ''' STAR  --runMode alignReads
    --runThreadN 8
    --genomeDir %(STARrmRep_repbase)s
    --genomeLoad LoadAndRemove
    --limitBAMsortRAM 10000000000
    --readFilesIn %(infile)s
    --outSAMunmapped Within
    --outFilterMultimapNmax 30
    --outFilterMultimapScoreRange 1
    --outFileNamePrefix %(outprefix)s
    --outSAMattributes All
    --readFilesCommand zcat
    --outStd BAM_Unsorted
    --outSAMtype BAM SortedByCoordinate
    --outFilterType BySJout
    --outReadsUnmapped Fastx
    --outFilterScoreMin 10
    --alignEndsType EndToEnd
    > %(outfile)s
    '''
    P.run()


# Count Reps
@follows(STARrmRep)
@transform(STARrmRep, suffix('.rep.bam'), '.metrics')
def countRep(infile, outfile):
    '''counts number reads mapping to each rep element'''
    statement = '''
    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2/bin
    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2
    samtools view %(infile)s | 
    /t1-data/user/nsampaio/software/gscripts/gscripts/general/count_aligned_from_sam.py 
    > %(outfile)s
    '''
    P.run()
   
# ---------------------------------------------------
# Generic pipeline tasks



def main(argv=None):
    if argv is None:
        argv = sys.argv
    P.main(argv)


if __name__ == "__main__":
    sys.exit(P.main(sys.argv))
