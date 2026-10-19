# RDH source acquisition (Phase 2)

This is a controlled *data acquisition* component, not redistricting analysis.
It does not run ReCom, choose an election field, join precinct polygons, or
certify the legality, neutrality, convergence, or accuracy of any ensemble.
Pennsylvania remains `pending_data` in `configs/states.json`.

The interface reuses the `RDH_API_SET_PARAMS.ipynb` approach in this repository:
`GET /wp-json/download/list?states=Pennsylvania&format=csv` for the listing,
then the selected `download/file/...` endpoint with its dataset ID. The older
`Download_API.txt` documents `datasetid` for restricted listing. Our state
query follows the official RDH notebook; if the provider changes that behavior,
this inventory stage must be updated. Access requires **designated RDH API-user
approval**, not merely a verified RDH account.

## 1. View the Pennsylvania source checklist (no account required)

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage sources
```

## 2. Obtain an authenticated catalog listing (approved API users only)

In PowerShell, enter credentials interactively. Do **not** paste them into a
GitHub file, commit, terminal command line, or ChatGPT conversation.

```powershell
$env:RDH_USERNAME = Read-Host "RDH API username"
$pw = Read-Host "RDH API password" -AsSecureString
$env:RDH_PASSWORD = [System.Net.NetworkCredential]::new("", $pw).Password
.\.venv\Scripts\python.exe main.py --penn --stage inventory --rdh-filter "2024 General Election"
Remove-Item Env:RDH_PASSWORD
Remove-Item Env:RDH_USERNAME
```

For an offline dry run, use `--dry-run` on the inventory stage.
The listing is saved to `data/external/rdh/pennsylvania/catalog.json`, which
is ignored by Git. The listing includes safe metadata (dataset IDs and download
paths only), **not** credential-bearing URLs or credentials. No auto-selection
of a scientifically valid dataset is performed.

## 3. Download a uniquely named catalog entry

Use a `filename` printed by inventory or found in its JSON catalog. Review the
entry before downloading; duplicate filenames are rejected.

```powershell
.\.venv\Scripts\python.exe main.py --penn --stage download --rdh-file "EXACT_FILE_FROM_CATALOG.zip" --dry-run
```

Remove `--dry-run` only after verifying the selection and setting the RDH
environment variables. Each file gets a `.receipt.json` recording the SHA-256,
byte count, dataset ID, and `DOWNLOADED_NOT_VALIDATED` status. Existing files
are never overwritten.

**Security caveat:** The upstream RDH API authenticates using query parameters,
so credentials necessarily enter the HTTPS request URL at the provider and
may appear in provider-side access logs. This client suppresses full URL
logging and sanitizes errors, but it cannot redesign the provider's protocol.
Avoid untrusted HTTP proxies and never publish request traces.

**Scope and limitations:** API metadata is not evidence that source files
match in year or geography. After download, separately verify 2020 population,
2024 precinct election totals, precinct shapes, block equivalency, 2022
congressional district assignments, and district-level checks before setting
Pennsylvania to a runnable status. A state with no comparable mid-decade redraw
is a replication/control case, not interchangeable with Texas/NC.
