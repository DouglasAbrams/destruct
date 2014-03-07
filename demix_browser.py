
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import random
import itertools
import seaborn


chromosomes = [str(a) for a in range(1, 23)] + ['X']
chromosome_indices = dict([(chromosome, idx) for idx, chromosome in enumerate(chromosomes)])

cnv = pd.read_csv('/Users/amcphers/Analysis/demix_interactive/patient_3.preds.tsv', sep='\t', converters={'chr':str})

cnv = cnv.loc[(cnv['library_id'] == 'adnexa_site_1')]
cnv = cnv.loc[(cnv['chr'].isin(chromosomes))]

cnv['chr_index'] = cnv['chr'].apply(lambda a: chromosome_indices[a])

cnv = cnv.sort(['chr_index', 'start'])

chromosome_length = cnv.groupby('chr', sort=False)['end'].max()
chromosome_end = np.cumsum(chromosome_length)
chromosome_start = chromosome_end.shift(1)
chromosome_start[0] = 0

cnv.set_index('chr', inplace=True)
cnv['chromosome_start'] = chromosome_start
cnv['chromosome_end'] = chromosome_end
cnv.reset_index(inplace=True)

cnv['chromosome_mid'] = 0.5 * (cnv['chromosome_start'] + cnv['chromosome_end'])

cnv['start'] += cnv['chromosome_start']
cnv['end'] += cnv['chromosome_start']

mingap = 1000

copies_max = 4.0





fig = plt.figure(figsize=(16,16))

gs = matplotlib.gridspec.GridSpec(2, 1, height_ratios=(4, 1))

ax1 = plt.subplot(gs[0])
ax2 = plt.subplot(gs[1])

color_set = plt.get_cmap('Set1')
color_set = [color_set(float(i)/len(chromosomes)) for i in range(len(chromosomes))]
chromosome_color = lambda c: color_set[chromosomes.index(c)]
cs = [chromosome_color(c) for c in cnv['chr'].values]
            
major_minor_scatter = ax1.scatter(cnv['major_raw'], cnv['minor_raw'],
                                  s=cnv['length']/20000.0, 
                                  facecolor=cs, edgecolor=cs, linewidth=0.0,
                                  picker=True)

ax1.set_xlim((-0.5, copies_max))
ax1.set_ylim((-0.5, 0.8*copies_max))

lgnd = ax1.legend([plt.Circle((0, 0), radius=1, color=chromosome_color(c), picker=True) for c in chromosomes], chromosomes, loc=2)
lgnd_patches = list(lgnd.get_patches())

for patch in lgnd_patches:
    patch.set_picker(True)

major_segments = list()
minor_segments = list()
major_connectors = list()
minor_connectors = list()

for (idx, row), (next_idx, next_row) in itertools.izip_longest(cnv.iterrows(), cnv.iloc[1:].iterrows(), fillvalue=(None, None)):
    major_segments.append([(row['start'], row['major_raw']), (row['end'], row['major_raw'])])
    minor_segments.append([(row['start'], row['minor_raw']), (row['end'], row['minor_raw'])])
    if next_row is not None and next_row['start'] - row['end'] < mingap and next_row['chr'] == row['chr']:
        major_connectors.append([(row['end'], row['major_raw']), (next_row['start'], next_row['major_raw'])])
        minor_connectors.append([(row['end'], row['minor_raw']), (next_row['start'], next_row['minor_raw'])])

major_segments = matplotlib.collections.LineCollection(major_segments, colors='r')
minor_segments = matplotlib.collections.LineCollection(minor_segments, colors='b')
major_connectors = matplotlib.collections.LineCollection(major_connectors, colors='r')
minor_connectors = matplotlib.collections.LineCollection(minor_connectors, colors='b')

major_segments.set_picker(True)
minor_segments.set_picker(True)

linewidths = np.array([1] * len(cnv.index))
major_minor_scatter.set_linewidths(linewidths)
major_segments.set_linewidths(linewidths)
minor_segments.set_linewidths(linewidths)

scatter_edgecolors = np.array(['b'] * len(cnv.index))
major_minor_scatter.set_edgecolors(scatter_edgecolors)
major_minor_scatter.set_zorder([1] * len(cnv.index))

ax2.add_collection(major_segments)
ax2.add_collection(minor_segments)
ax2.add_collection(major_connectors)
ax2.add_collection(minor_connectors)
ax2.set_xlim((cnv['start'].min(), cnv['end'].max()))
ax2.set_ylim((-0.2, copies_max + 0.2))

ax2.set_xticks([0] + sorted(cnv['chromosome_end'].unique()))
ax2.set_xticklabels([])

ax2.xaxis.set_minor_locator(matplotlib.ticker.FixedLocator(sorted(cnv['chromosome_mid'].unique())))
ax2.xaxis.set_minor_formatter(matplotlib.ticker.FixedFormatter(chromosomes))

ax2.grid(False, which="minor")

class Picker(object):
    def __init__(self):
        self.selected_chromosome = None
    def __call__(self, event):
        if isinstance(event.artist, matplotlib.patches.Rectangle):
            try:
                ind = lgnd_patches.index(event.artist)
            except ValueError:
                return
            chromosome = chromosomes[ind]
            
            # Unhighlight currently selected chromosome if necessary
            if self.selected_chromosome is not None:
                lgnd_patches[chromosomes.index(self.selected_chromosome)].set_edgecolor((0, 0, 0, 0))

            # Clicking on the chromosome again unselects it
            if chromosome == self.selected_chromosome:
                self.unselect_chromosome()
            else:
                self.select_chromosome(chromosome)

        elif isinstance(event.artist, matplotlib.collections.PathCollection) or isinstance(event.artist, matplotlib.collections.LineCollection):
            linewidths = np.array([1] * len(cnv.index))
            linewidths[event.ind] = 4
            scatter_edgecolors = np.array(['b'] * len(cnv.index))
            scatter_edgecolors[event.ind] = 'yellow'
            major_minor_scatter.set_edgecolors(scatter_edgecolors)
            major_minor_scatter.set_linewidths(linewidths)
            major_segments.set_linewidths(linewidths)
            minor_segments.set_linewidths(linewidths)

        event.canvas.draw()

    def select_chromosome(self, chromosome):

        ind = chromosomes.index(chromosome)

        # Highlight currently selected chromosome 
        lgnd_patches[ind].set_edgecolor('yellow')
        lgnd_patches[ind].set_linewidth(2)

        # Restrict x axis to current chromosome view
        ax2.set_xlim((chromosome_start[chromosome], chromosome_end[chromosome]))
        ticks = np.arange(0, chromosome_length[chromosome], 10000000)
        ax2.set_xticks(ticks + chromosome_start[chromosome])
        ax2.set_xticklabels([str(a/1000000) for a in ticks])

        self.selected_chromosome = chromosome

    def unselect_chromosome(self):

        # Redo xaxis for full view
        ax2.set_xlim((cnv['start'].min(), cnv['end'].max()))
        ax2.set_xticks([0] + sorted(cnv['chromosome_end'].unique()))
        ax2.set_xticklabels([])
        ax2.xaxis.set_minor_locator(matplotlib.ticker.FixedLocator(sorted(cnv['chromosome_mid'].unique())))
        ax2.xaxis.set_minor_formatter(matplotlib.ticker.FixedFormatter(chromosomes))
        ax2.grid(False, which="minor")

        self.selected_chromosome = None


            
fig.canvas.mpl_connect('pick_event', Picker())


plt.show()

