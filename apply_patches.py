import os

def patch_file(path, target, replacement):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if target in content:
        new_content = content.replace(target, replacement)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ Successfully patched {os.path.basename(path)}")
    else:
        print(f"❌ Failed to find target in {os.path.basename(path)}")

# 1. Patch run.py
target_run = """        filters = {
            "start_date": request.args.get('start_date'),
            "end_date": request.args.get('end_date'),
            "borough": request.args.get('borough', 'all')
        }"""
replacement_run = """        filters = {
            "start_date": request.args.get('start_date'),
            "end_date": request.args.get('end_date'),
            "borough": request.args.get('borough', 'all'),
            "zone_id": request.args.get('zone_id')
        }"""
patch_file('backend/run.py', target_run, replacement_run)

# 2. Patch app.js (URL params)
target_app_url = "if (borough !== 'all') url.searchParams.append('borough', borough);"
replacement_app_url = """if (borough !== 'all') url.searchParams.append('borough', borough);
        if (activeZoneId) url.searchParams.append('zone_id', activeZoneId);"""
patch_file('frontend/app.js', target_app_url, replacement_app_url)

# 3. Patch app.js (Summary grid)
target_app_grid = """                { label: 'Health Score', val: `${data.summary.systemHealth}%` },
                { label: 'Choke Points', val: data.summary.activeChokePoints }
            ];"""
replacement_app_grid = """                { label: 'Health Score', val: `${data.summary.systemHealth}%` },
                { label: 'Choke Points', val: data.summary.activeChokePoints }
            ];

            if (data.metadata.isZoneReport) {
                metrics.push({ label: 'Zone Speed', val: `${data.metadata.comparison.zoneSpeed} MPH` });
                metrics.push({ label: 'Borough Speed', val: `${data.metadata.comparison.boroughSpeed} MPH` });
                metrics.push({ label: 'Var vs Borough', val: `${data.metadata.comparison.diff}%` });
            }"""
patch_file('frontend/app.js', target_app_grid, replacement_app_grid)

# 4. Patch app.js (Table Title)
target_app_title = "const tbody = document.querySelector('#reportTopZones tbody');"
replacement_app_title = """// Populate Top Zones
            const reportTableTitleArea = document.querySelector('#reportTopZones');
            if (reportTableTitleArea) {
                const h4 = reportTableTitleArea.previousElementSibling;
                if (h4 && h4.tagName === 'H4') {
                    h4.textContent = data.metadata.isZoneReport ? "Top Destination Zones" : "Top Zones by Trip Volume";
                }
            }
            const tbody = document.querySelector('#reportTopZones tbody');"""
patch_file('frontend/app.js', target_app_title, replacement_app_title)
鼓
