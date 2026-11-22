"""Plot existing terrain-stratum diagnostics with QGIS Python (no downloads)."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/multiyear_2023_2025/surface_patterns'


def main():
    with (OUT/'terrain_strata_statistics.csv').open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
    for column,terrain in enumerate(['slope_degrees','twi']):
        selected=[r for r in rows if r['terrain']==terrain]
        if len(selected)!=3:raise RuntimeError('Expected three terrain groups')
        for field,label,color in [('pre_ndmi_median','Pre-monsoon','#b66b28'),('post_ndmi_median','Post-monsoon','#008b8b')]:
            axes[0,column].plot(range(3),[float(r[field]) for r in selected],marker='o',label=label,color=color)
        for field,label,color in [('median_ndmi_change','NDMI','#008b8b'),('ndvi_change_median','NDVI','#5a963b')]:
            axes[1,column].plot(range(3),[float(r[field]) for r in selected],marker='o',label=label,color=color)
        for ax in axes[:,column]:
            ax.set_xticks(range(3),['Lower third','Middle third','Upper third'])
            ax.axhline(0,color='gray',linewidth=.7);ax.grid(alpha=.2);ax.legend()
        axes[0,column].set_title('Slope groups' if column==0 else 'TWI groups')
    axes[0,0].set_ylabel('Median seasonal NDMI level')
    axes[1,0].set_ylabel('Median within-year seasonal change')
    fig.suptitle('Venkatapur 2023–2025: terrain and surface indicators\nCommon valid pixels; recurrent SCL-water excluded. Descriptive, not groundwater suitability.')
    fig.savefig(OUT/'terrain_surface_review.png',dpi=180)
    fig.savefig(OUT/'terrain_surface_review.pdf')
    plt.close(fig)
    print('Saved terrain_surface_review.png and .pdf')


if __name__=='__main__':main()
