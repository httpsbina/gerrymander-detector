# NC clean-room reproduction

I cloned the published paper branch from GitHub into a fresh workspace and downloaded the frozen NC inputs and Python runtime from the draft continuation release. I created a new environment and installed every version in the pinned requirements file, without copying packages or scientific inputs from my working checkout.

I reproduced all six NC figures and all four paper tables byte for byte, and every value in the complete paper `results.json` matched. All 81 frozen file checksums matched, and the environment dependency check passed.

## Records

The repository commit, archive hashes, package versions, commands and comparison results are in `verification.json`. `environment-installed.txt` records the fresh installation.

## Limitations

The test ran on the same ARM Mac, so it does not certify a different platform. GitHub authentication was required for the draft assets, and the fresh installation used PyPI in addition to the repository and release. Git and an archive extractor were available on the machine. The fresh checkout had no optional Prettier installation; JSON serialization differed, though all values matched exactly.
