"""Offline daily rainfall and prior-complete-UTC-day acquisition context."""
import csv
from datetime import date, timedelta
import json
from pathlib import Path

from extract_imerg_month import validate_day, CELLS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/rainfall_context'


def prior_window(daily, acquired, cell, days):
    values = [daily.get((acquired-timedelta(days=i), cell)) for i in range(1, days+1)]
    valid = [v for v in values if v is not None]
    return len(valid), sum(valid) if len(valid) == days else ''


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    daily, rows = {}, []
    for n in range(1, 32):
        day = date(2025, 5, n)
        info = validate_day(day)
        if info is None:
            raise RuntimeError('Complete May data required: '+day.isoformat())
        for cell in sorted(CELLS):
            values = info['cells'][cell]
            amount = values['observed_mm'] if values['valid_intervals'] == 48 else None
            daily[day, cell] = amount
            rows.append(dict(date_utc=day.isoformat(), longitude=cell[0], latitude=cell[1],
                             valid_intervals=values['valid_intervals'], daily_mm=amount if amount is not None else ''))
    write_csv(OUT/'daily_rainfall_2025_05.csv', rows)
    context = []
    for sensor, filename in [('Sentinel-2', 's2_seasons_2025/seasonal_manifest.json'),
                             ('Sentinel-1', 's1_seasons_2025/radar_manifest.json')]:
        manifest = json.loads((ROOT/'data/processed'/filename).read_text())
        for season in manifest['seasons'].values():
            for observation in season['observations']:
                acquired = date.fromisoformat(observation['date'])
                if (acquired.year, acquired.month) != (2025, 5):
                    continue
                for cell in sorted(CELLS):
                    row = dict(sensor=sensor, acquisition_date=acquired.isoformat(), longitude=cell[0], latitude=cell[1])
                    for days in [1, 3, 7, 14]:
                        count, total = prior_window(daily, acquired, cell, days)
                        row[f'prior_{days}d_valid_days'] = count
                        row[f'prior_{days}d_mm'] = total
                    context.append(row)
    write_csv(OUT/'may_acquisition_rainfall_context.csv', context)
    notes = '''# May 2025 rainfall context

Daily totals integrate 48 half-hour IMERG V07 precipitationUncal rates (mm/hour times 0.5 hours). Cells are reported separately; no village average or recharge estimate is calculated.

Acquisition context uses the previous 1, 3, 7 and 14 complete UTC calendar days, excluding the acquisition day to avoid including rain after the image. These are calendar-day windows, not exact trailing hours. Incomplete windows remain blank, with valid-day counts recorded. April is unavailable; no missing days are treated as zero.

Only May observations selected in the existing seasonal manifests are included. Rainfall context does not by itself demonstrate a relationship with individual image values or explain the March-May seasonal composite. Irrigation, crop growth, soil and radar roughness remain possible confounders. No groundwater score, causal attribution or MCDA weights are produced.

The uncalibrated field omits monthly gauge adjustment; ancillary calibration/models remain. One month is not a seasonal or multi-year rainfall baseline. Outputs are generated locally without login or network access.
'''
    (OUT/'may_context_notes.md').write_text(notes, encoding='utf-8')
    print(f'Saved {len(rows)} daily cell totals and {len(context)} acquisition/cell context rows to {OUT}')


if __name__ == '__main__':
    main()
