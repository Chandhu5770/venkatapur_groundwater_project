"""Compare water-screening assumptions locally; run with QGIS Python."""
import json
from pathlib import Path

import numpy as np
from osgeo import gdal

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/processed/s2_trial_2025'
OUT = BASE / 'water_mask_audit'
DATES = ['2025-05-12', '2025-12-28']


def main():
    gdal.UseExceptions()
    OUT.mkdir(parents=True, exist_ok=True)
    reference = gdal.Open(str(BASE / (DATES[0] + '_NDMI.tif')))

    def read(path):
        ds = gdal.Open(str(path))
        assert ds.GetGeoTransform() == reference.GetGeoTransform()
        assert ds.GetProjection() == reference.GetProjection()
        a = ds.ReadAsArray().astype(float)
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        if nodata is not None:
            a[a == nodata] = np.nan
        return a

    def save(name, array):
        ds = gdal.GetDriverByName('GTiff').Create(str(OUT / (name + '.tif')),
            reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Float32,
            options=['COMPRESS=DEFLATE', 'TILED=YES'])
        ds.SetGeoTransform(reference.GetGeoTransform())
        ds.SetProjection(reference.GetProjection())
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(np.where(np.isfinite(array), array, -9999).astype('float32'))
        ds = None

    def stats(a, selection):
        values = a[selection & np.isfinite(a)]
        return {'pixels': int(values.size), 'area_km2': float(values.size * 400 / 1e6),
                'median': float(np.median(values)) if values.size else None}

    report = {'scope': 'Two-date water-mask sensitivity audit; no confirmed water labels or groundwater inference.',
        'class_legend': {'0': 'Neither method flags water', '1': 'SCL water and MNDWI > 0',
                         '2': 'SCL water only', '3': 'MNDWI > 0 only: requires review'},
        'dates': {}, 'paired_scenarios': {}}
    masks, ndmis = {}, {}
    for date in DATES:
        scl = read(ROOT / 'data/raw/sentinel/s2/trial_2025' / date / 'SCL.tif')
        quality = read(BASE / (date + '_quality_mask.tif')) == 1
        ndvi = read(BASE / (date + '_NDVI.tif'))
        ndmi = read(BASE / (date + '_NDMI.tif'))
        mndwi = read(BASE / (date + '_MNDWI.tif'))
        s = quality & (scl == 6)
        m = quality & np.isfinite(mndwi) & (mndwi > 0)
        extra = m & ~s
        classes = np.where(quality, 0.0, np.nan)
        classes[s & m] = 1
        classes[s & ~m] = 2
        classes[extra] = 3
        save(date + '_method_agreement', classes)
        assert not np.any(s & ~quality)
        original = read(BASE / (date + '_water_flag.tif'))
        assert np.array_equal(original[quality] == 1, (s | m)[quality])
        details = {'eligible_pixels': int(quality.sum()), 'scl_water_pixels': int(s.sum()),
            'broad_union_pixels': int((s | m).sum()), 'mndwi_only_pixels': int(extra.sum()),
            'mndwi_only_by_scl': {str(int(k)): int((extra & (scl == k)).sum()) for k in np.unique(scl[extra])},
            'ndvi_in_mndwi_only': stats(ndvi, extra),
            'ndmi_in_mndwi_only': stats(ndmi, extra),
            'mndwi_only_ndvi_above_0_3_pixels': int((extra & (ndvi > .3)).sum())}
        report['dates'][date] = details
        masks[date] = {'scl_only': s, 'scl_or_mndwi_gt_0': s | m,
                       'scl_or_mndwi_gt_0_2': s | (quality & (mndwi > .2))}
        ndmis[date] = ndmi
    pre, post = DATES
    delta = ndmis[post] - ndmis[pre]
    common = np.isfinite(delta)
    for name in masks[pre]:
        eligible = common & ~masks[pre][name] & ~masks[post][name]
        report['paired_scenarios'][name] = stats(delta, eligible)
        save('post_minus_pre_NDMI_' + name, np.where(eligible, delta, np.nan))
    report['decision'] = ('Retain SCL-only, broad union, and threshold-0.2 as named sensitivity scenarios. '
        'Treat MNDWI-only pixels as uncertain surface evidence; do not label them confirmed open water. '
        'No scenario is ground truth. NDVI>0.3 is a descriptive vegetation check, not an irrigation classifier. '
        'Use seasonal water frequency and imagery review before persistent-water exclusions.')
    (OUT / 'audit_results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    write_review_project()
    lines = ['Water-mask sensitivity audit', '', report['scope'], '']
    for date, d in report['dates'].items():
        lines.append(f"{date}: SCL water={d['scl_water_pixels']}; broad union={d['broad_union_pixels']}; MNDWI-only={d['mndwi_only_pixels']}")
        lines.append('MNDWI-only pixels by SCL: ' + str(d['mndwi_only_by_scl']))
    lines.extend(['', 'NDMI change is December minus May, excluding flags on either date.'])
    for name, d in report['paired_scenarios'].items():
        lines.append(f"{name}: {d['pixels']} paired pixels; median NDMI change={d['median']:.5f}")
    lines.extend(['', report['decision']])
    (OUT / 'audit_report.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))


def write_review_project():
    from qgis.core import (QgsApplication, QgsProject, QgsRasterLayer, QgsColorRampShader,
        QgsRasterShader, QgsSingleBandPseudoColorRenderer, QgsReferencedRectangle)
    from qgis.PyQt.QtGui import QColor
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    project.setTitle('Water flag disagreement: two-date optical trial')
    labels = ['Neither flags water', 'Both flag water', 'SCL only', 'MNDWI only - uncertain']
    colors = ['#eeeeee', '#2166ac', '#67a9cf', '#e66101']
    for date in DATES:
        layer = QgsRasterLayer(str(OUT / (date + '_method_agreement.tif')), date + ' water flag agreement')
        assert layer.isValid()
        ramp = QgsColorRampShader()
        ramp.setColorRampType(QgsColorRampShader.Exact)
        ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(i, QColor(c), label)
                                  for i, (c, label) in enumerate(zip(colors, labels))])
        shader = QgsRasterShader(0, 3)
        shader.setRasterShaderFunction(ramp)
        layer.setRenderer(QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader))
        project.addMapLayer(layer)
        project.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(date == DATES[-1])
        project.setCrs(layer.crs())
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(layer.extent(), layer.crs()))
    assert project.write(str(OUT / 'water_mask_audit.qgz'))


if __name__ == '__main__':
    main()
