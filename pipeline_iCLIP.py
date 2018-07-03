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
need to change env name from py36-v1 to desired one'''
   
# PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/py36-v1/bin
# CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/py36-v1
  
# Demultiplexing
@split('*.fastq.gz', '*.demux.fastq.gz')
def demux(infile, outfiles):    
    ''' demultiplex and move UMI to end of header using iCount '''
    startfile = " ".join(infile)
    statement = ''' 
    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/iCount/bin
    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/iCount
    iCount demultiplex %(startfile)s
    %(adapter)s
    %(demux_barcodes)s
    --out_dir "%(general_outputdir)s"
    '''
    P.run()


# Cutadapt
@follows(demux)
@transform('*NN.fastq.gz', regex(r'demux_NNN(.*)NN.fastq.gz'), r'\1.trim.fastq.gz') 
def cutadapt(infile, outfile):
    ''' trims 3' adapter and removes low quality reads '''
    statement = ''' cutadapt -q %(cutadapt_minphred)s 
    --minimum-length %(cutadapt_minlength)s 
    -a %(general_adapter)s
    -o %(outfile)s %(infile)s
    '''
    P.run()


# STAR remove Reps
@follows(mkdir("mappedreps"))
@transform(cutadapt, regex(r'(\S+).trim.fastq.gz'), r'mappedreps/\1.rep.bam')
def STARrmRep(infile, outfile):
    ''' maps to repetitive elements, produces 2 files:
        mapped - file1.name; unmapped file2.name '''
    outprefix = P.snip(outfile, ".bam")
    statement = ''' STAR  --runMode alignReads
    --runThreadN 8
    --genomeDir %(STARrmRep_repbase)s
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
#@follows(STARrmRep)
#@transform(STARrmRep, suffix('.rep.bam'), '.metrics')
#def countRep(infile, outfile):
#    '''counts number reads mapping to each rep element'''
#    statement = '''
#    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2/bin
#    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2
#    samtools view %(infile)s | 
#    /t1-data/user/nsampaio/software/gscripts/gscripts/general/count_aligned_from_sam.py 
#    > %(outfile)s
#    '''
#    P.run()
    
    
# FASTQC
@follows(STARrmRep)
@transform('*repUnmapped.out.mate1', regex(r'(.*).repUnmapped.out.mate1'), r'\1.fastqc')
def fastqc2(infile,outfile):
    ''' does fastqc on mapped repetitive elements from STARrmRep '''
    statement = ''' fastqc %(infile)s -o %(fastqc2_fastqcdir)s > %(outfile)s
    '''
    P.run()


# STAR mapping
@follows(STARrmRep)
@follows(mkdir("STARmapped"))
@transform('*.repUnmapped.out.mate1', regex(r'(.*).repUnmapped.out.mate1'), r'STARmapped/\1.bam')
def STARmap(infile,outfile):
    ''' maps non-repetitive elements to genome '''
    outprefix = P.snip(outfile, ".bam")
    statement = ''' STAR  --runMode alignReads
    --runThreadN 8
    --genomeDir %(STARmap_genome)s
    --readFilesIn %(infile)s
    --outSAMunmapped Within
    --outFilterMultimapNmax 1
    --outFilterMultimapScoreRange 1
    --outFileNamePrefix %(outprefix)s
    --outSAMattributes All
    --outStd BAM_Unsorted
    --outSAMtype BAM Unsorted
    --outFilterType BySJout
    --outReadsUnmapped Fastx
    --outFilterScoreMin 10
    --outSAMattrRGline ID:foo
    --alignEndsType EndToEnd
    > %(outfile)s 
    '''
    P.run()

#samtools sort
@transform(STARmap, suffix('.bam'), '.sorted.bam')
def samtools_sort(infile, outfile):
    statement = ''' samtools sort %(infile)s -o %(outfile)s
    '''
    P.run()
    
# samtools index1
@follows(samtools_sort)
@transform(samtools_sort, suffix('.sorted.bam'), '.sorted.bam.bai')
def index1(infile, outfile):
    statement = ''' samtools index %(infile)s
    '''
    P.run()


# Deduplicate
@follows(index1)
@transform('*.sorted.bam', regex(r'(.*).sorted.bam'), r'\1.dedup.bam')
def dedup(infile,outfile):
    ''' deduplicate samples based on UMI using umi_tools '''
    statement = ''' umi_tools dedup -I %(infile)s --output-stats=deduplicated -S %(outfile)s
    '''
    P.run()


# samtools index2
@transform(dedup, suffix('.dedup.bam'), 'dedup.bam.bai')
def index2(infile, outfile):
    ''' creates index deduplicated bam file, generates .bai '''
    statement = '''samtools index %(infile)s
    '''
    P.run()

# Make bigwig
@follows(index2)
@transform(sort, suffix('.sorted.bam'), '.bw') ### might not work due to only having Read 1
def makeBigWig(infile, outfile):
    ''' Makes bigwig files for visualization '''
    statement = ''' 
    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2/bin
    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2
    make_bigwig_files.py
    --bam %(infile)s
    --genome %(general_chromsize)s
    --bw_pos %(outfile)
    '''
    P.run()
  

# Call peaks
@follows(index)
@transform(sort, suffix('.sorted.bam'), '.bed')
def callPeaks(infile, outfile):
    ''' Calls peaks using CLIPper package'''
    statement = '''
    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/clipper/bin
    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/envs/clipper
    CLIPPER COMMANDS
    '''
    P.run() ###### need to get clipper to work and figure out commands

# Fix scores
@transform(callPeaks, suffix('.bed'), '.fixed.bed')
def fixScores(infile, outfile):
    ''' Fixes p-values to be bed compatible '''
    statement = ''' 
    PATH=/t1-data/user/nsampaio/py36-v1/conda-install/envs/Py2/bin
    CONDA_PREFIX=/t1-data/user/nsampaio/py36-v1/conda-install/Py2/iCount
    python ~/gscripts/gscripts/clipseq/fix_scores.py
    --bed %(infile)s
    --out_%(outfile)s
    '''
    P.run()

# Bed to BigBed
@transform(fixScores, suffix('.fixed.bed'), '.fixed.bb')
def bigBed(infile, outfile):
    ''' Converts bed file to bigBed file for uploading to the genomeBrowser '''
    statement = ''' bedToBigBed %(infile)s
    %(general_chromsize)s
    %(outfile)s
    -type=bed6+4
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
