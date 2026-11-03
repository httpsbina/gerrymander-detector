# RDH source acquisition

I use the RDH catalog and download endpoints to inventory source files, retaining dataset IDs, byte counts, and SHA-256 receipts. The interface follows `RDH_API_SET_PARAMS.ipynb`: `GET /wp-json/download/list?states=Pennsylvania&format=csv`, followed by the selected `download/file/...` endpoint. `Download_API.txt` records the `datasetid` parameter.

## Source checklist

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage sources
```

## Catalog

I enter account credentials interactively and keep them outside source control.

```powershell
$env:RDH_USERNAME = Read-Host "RDH API username"
$pw = Read-Host "RDH API password" -AsSecureString
$env:RDH_PASSWORD = [System.Net.NetworkCredential]::new("", $pw).Password
.\.venv\Scripts\python.exe main.py --penn --stage inventory --rdh-filter "2024 General Election"
Remove-Item Env:RDH_PASSWORD
Remove-Item Env:RDH_USERNAME
```

I use `--dry-run` for an offline inventory. The catalog is saved to `data/external/rdh/pennsylvania/catalog.json`, with dataset IDs and download paths.

## Download

I select an exact catalog filename, check for duplicate names, and inspect the dry run before downloading.

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage download --rdh-file "EXACT_FILE_FROM_CATALOG.zip" --dry-run
```

I remove `--dry-run` to download the selected entry. Its `.receipt.json` records SHA-256, bytes, dataset ID, and the `DOWNLOADED_NOT_VALIDATED` status; existing files are preserved.

## Limitations

I validate year, geography, 2020 population, 2024 precinct election totals, shapes, block equivalency, 2022 congressional assignments, and district totals after acquisition. Catalog metadata alone leaves those checks open. Pennsylvania remains `pending_data`; a state with no comparable mid-decade redraw serves a different comparison from Texas or NC. The provider places account credentials in request URLs, so I keep request traces outside the published records.
