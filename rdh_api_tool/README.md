# RDH API tools

I retain these notebooks from the [Redistricting Data Hub API repository](https://github.com/nonpartisan-redistricting-datahub/api), with the provider's WordPress API notes in `Download_API.txt`. RDH wrote the notebooks; I use them to retrieve source data.

## Files and execution

- `RDH_API.ipynb`: interactive account and search-parameter entry.
- `RDH_API_SET_PARAMS.ipynb`: parameters set at the top of the notebook.
- `Download_API.txt`: provider endpoint documentation.

I run the selected notebook from its directory, where it writes the downloaded files. The notebooks use pandas, requests, io, numpy and getpass; the recorded package versions are pandas 1.3.1, requests 2.25.1 and numpy 1.20.3. I keep dataset details with the state pages at [RDH](https://redistrictingdatahub.org), and the provider contact is info@redistrictingdatahub.org.

## Limitations

The notebooks require designated API access, which differs from a verified website account. I keep account details outside Git; the local credential-bearing `download_texas.py` is excluded. These notebook versions describe the provider tools, while the research environment has its own pinned package set.
