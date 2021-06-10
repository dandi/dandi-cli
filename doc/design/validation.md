# Requirements for being a valid DANDI asset

## General
1. All assets must have a non-zero file size.

## NWB files
- subject id
- age in iso8601 interval format or datetime of birth
- age reference 
- sex

### NWB organization disambiguation requirements

At least one of the following should be present. in case of having to disambiguate
- session
- sample
- cell
- probe
- task (not in nwb at the moment, but we could use session timestamp)


## BIDS datasets



