"""Build a compact review PDF from checked local outputs. Run with QGIS Python."""
import csv
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/processed'
OUT=DATA/'integrated_evidence_review'


def load(relative):
    with (DATA/relative).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet();story=[]
    def para(text,style='BodyText'):
        story.append(Paragraph(escape(text),styles[style]));story.append(Spacer(1,8))
    def table(rows):
        rendered=[[Paragraph(escape(str(v)),styles['BodyText']) for v in row] for row in rows]
        t=Table(rendered,colWidths=[2.0*inch,4.6*inch],repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e0eff0')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),
            ('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7)]))
        story.append(t);story.append(Spacer(1,10))
    rain=load('rainfall_context/imerg_uncal_2025_05.csv')
    if len(rain)!=2 or not all(r['complete']=='True' and int(r['valid_intervals'])==1488 for r in rain):
        raise RuntimeError('Complete May rainfall required')
    temporal=load('multiyear_2023_2025/surface_patterns/temporal_consistency_statistics.csv')
    optical=load('multiyear_2023_2025/surface_patterns/optical_confounding_statistics.csv')
    sensitivity=load('terrain_scenarios/weight_sensitivity.csv')
    def comparison(a,b):
        return next(r for r in sensitivity if r['first']==a and r['second']==b)
    para('Venkatapur satellite screening: analysis review','Title')
    para('Evidence snapshot: 22 November 2026. Analysis period 2023-2025; rainfall context May 2025 only.')
    para('This is an exploratory relative screening pilot, not a validated groundwater-potential map. Satellites do not directly detect groundwater or establish borewell yield, drilling depth or guaranteed water.')
    table([['Component','Completed / practical limit'],
        ['Study area','User-confirmed centre and 5 km planning buffer; village boundary remains unverified.'],
        ['Optical and radar','Sampled pre/post seasonal indicators for 2023-2025. Planned 2021-2025 baseline remains incomplete.'],
        ['Terrain','Copernicus GLO-30 DSM, slope, TWI and drainage diagnostics; uncertain upstream estimates excluded.'],
        ['Rainfall','Two native IMERG uncalibrated cells, all 31 May days complete. No village average, recharge estimate or seasonal baseline.'],
        ['MCDA','Ten hypothetical terrain-only scenarios; no final terrain-plus-surface weights or selected groundwater classes.']])
    para('May native-cell totals: '+ '; '.join(f"latitude {r['latitude']}, longitude {r['longitude']}: {float(r['monthly_total_mm']):.2f} mm" for r in rain)+'.')
    para('Rainfall and image context','Heading2')
    para('NDMI decreased by a median 0.0278 between 2 and 12 May on paired pixels despite about 17 mm estimated rain in the preceding seven days. Radar VV/VH increased by median 2.41/3.08 dB from 16 to 28 May, with 71-82 mm estimated rain in the seven days before 28 May. Coincidence does not establish causation; vegetation, irrigation, roughness and surface water remain confounders.')
    story.append(PageBreak())
    para('Terrain, moisture baseline and vegetation','Heading1')
    para('Flatter groups start with higher pre-monsoon NDMI; relatively steeper groups show larger changes in both NDMI and NDVI. Change magnitude alone is therefore not a defensible groundwater-suitability direction. Terrain thirds are local descriptive groups, not physical thresholds.')
    story.append(Image(str(DATA/'multiyear_2023_2025/surface_patterns/terrain_surface_review.png'),width=6.6*inch,height=4.8*inch))
    para('Seasonal levels and within-year changes use different median aggregation orders, so subtracting displayed level medians need not reproduce the summarized change. Both inputs and their limitations must remain visible.')
    selected=[r for r in optical if r['mask_scenario']=='scl_water_at_least_2_years' and r['threshold_scenario']=='strict_sign']
    same=sum(float(r['fraction_common']) for r in selected if r['category'] in ['both_increase','both_decrease'])
    para(f'Automated optical comparison: NDMI and NDVI change signs agree on {same*100:.2f}% of common pixels; rank correlation is {float(selected[0]["spearman_all_common"]):.3f}. Shared NIR bands prevent independent confirmation. This is not an irrigation classifier or groundwater validation.')
    para('Temporal consistency','Heading2')
    for key,label in [('s2_NDMI','NDMI'),('s1_vv','VV'),('s1_vh','VH')]:
        r=next(r for r in temporal if r['indicator']==key and r['code']=='3')
        para(f"{label}: {float(r['fraction_common'])*100:.1f}% of common pixels have mixed annual signs or at least one exactly zero seasonal change. Strict signs include tiny changes; consistency is not statistical confidence.")
    story.append(PageBreak())
    para('Sensitivity and decision limits','Heading1')
    rows=[['Test','Pixels changing upper-fifth membership']]
    for a,b,label in [('slope_emphasis','convergence_emphasis','Terrain weight extremes'),
        ('balanced_terrain','slope_only','Balanced vs slope alone'),('balanced_terrain','twi_only','Balanced vs TWI alone'),
        ('balanced_terrain','balanced_terrain_clipped_linear','Balanced: rank vs clipped-linear scaling')]:
        rows.append([label,f"{float(comparison(a,b)['fraction_membership_changed'])*100:.2f}% of identical common support"])
    table(rows)
    para('Upper fifth is a local exploratory score group, not a favorable groundwater class. Rank scaling and 2nd/98th-percentile clipped-linear scaling are alternative assumptions. Slope and TWI share DEM information; neither independently validates the other. No scenario is selected.')
    para('Drainage density also depends on extraction threshold: between 0.25 and 1.0 km2 contributing-area thresholds, 15.36% of common pixels change upper-density-third membership. Density coverage excludes uncertain upstream neighbourhoods.')
    para('Remaining work before stronger screening claims','Heading2')
    for text in ['Review a documented village boundary or retain the explicitly labelled planning buffer.',
        'Complete or explicitly narrow the planned time baseline and seasonal rainfall scope; May alone is not sufficient for multi-year rainfall attribution.',
        'Review crop, irrigation, built-up and persistent-water interpretation with source imagery; current proxy masks do not identify irrigation.',
        'If choosing a combined model, document defensible indicator directions, redundancy, exclusions and named sensitivity scenarios. Present the separate evidence alongside it.',
        'Independent hydrogeological/field assessment is needed for validation and drilling decisions; no supervised ML is justified without verified labels.']:
        para(text)
    para('Reproduction and review','Heading2')
    para('Open venkatapur_evidence_review.qgz in this folder; keep sibling processed folders in place. Consult docs/06_scenario_review.md and the scripts in src/. Inputs, rasters and reports remain Git-ignored. This PDF summarizes existing local results; it does not create new measurements or validation.')
    path=OUT/'venkatapur_analysis_review.pdf'
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.drawString(42,25,'Exploratory surface/terrain evidence | No groundwater depth or yield prediction')
        canvas.drawRightString(570,25,str(doc.page))
    SimpleDocTemplate(str(path),rightMargin=36,leftMargin=36,topMargin=32,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)
    print('Saved',path)


if __name__=='__main__':main()
