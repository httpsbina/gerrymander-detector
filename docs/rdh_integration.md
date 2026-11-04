# RDH source acquisition

I inventory RDH files before downloading them, keeping dataset IDs, byte counts and SHA-256 receipts with each source. I follow `RDH_API_SET_PARAMS.ipynb`: `GET /wp-json/download/list?states=Pennsylvania&format=csv` returns the catalog, and `download/file/...` selects a file. `Download_API.txt` describes the `datasetid` parameter.

## Reproducing

I list the required sources with:

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage sources
```

I enter credentials interactively and keep them outside source control:

```powershell
$env:RDH_USERNAME = Read-Host "RDH API username"
$pw = Read-Host "RDH API password" -AsSecureString
$env:RDH_PASSWORD = [System.Net.NetworkCredential]::new("", $pw).Password
.\.venv\Scripts\python.exe main.py --penn --stage inventory --rdh-filter "2024 General Election"
Remove-Item Env:RDH_PASSWORD
Remove-Item Env:RDH_USERNAME
```

I use `--dry-run` for an offline inventory. The catalog goes to `data/external/rdh/pennsylvania/catalog.json`, including dataset IDs and download paths. After selecting an exact filename and checking duplicate names, I inspect the download with:

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage download --rdh-file "EXACT_FILE_FROM_CATALOG.zip" --dry-run
```

I remove `--dry-run` to download that entry. Its `.receipt.json` records the hash, size, dataset ID and `DOWNLOADED_NOT_VALIDATED` status; existing files stay in place.

## Limitations

Acquisition leaves the year, geography, 2020 population, 2024 precinct votes, shapes, block equivalency, 2022 congressional assignments and district totals to be validated. Pennsylvania remains `pending_data`; without a comparable mid-decade redraw, it would answer a different comparison from Texas or NC. The provider includes credentials in request URLs, so I keep request traces outside published records.
