import csv
import io
import os
import re
import requests
import zipfile

# Long format field positions (1-indexed per spec, converted to 0-indexed slices)
# 1-4:    Contest Number
# 5-7:    Candidate Number
# 8-11:   Precinct Code
# 12-17:  Total Votes
# 18-23:  Group 1 Votes (Election Day)
# 24-29:  Group 2 Votes (Mail Ballots)
# 30-35:  Group 3 Votes (Early Voting)
# 102-104: Party Code
# 105-107: District Type ID
# 108-111: District Code
# 112-167: Contest Title
# 168-205: Candidate Name
# 206-235: Precinct Name
# 236-260: District Name
# 261-262: Votes Allowed
# 263:    Referendum Flag
#
# Short format has only fields 1-101 (numeric data, no descriptive text).
# A lookup table built from the long-format setup file is required to resolve
# contest title, candidate name, party, and precinct name by key (contest,
# candidate, precinct).

OFFICE_MAP = {
    'Presidential Electors For:': 'President',
    'Presidential Candidate': 'President',
    'Senator in Congress': 'U.S. Senate',
}

def normalize_office(title):
    # Primary contest titles are prefixed with the party code (e.g. "DEM Senator in Congress")
    stripped = re.sub(r'^[A-Z]{2,4}\s+', '', title)
    if stripped in OFFICE_MAP:
        return OFFICE_MAP[stripped]
    if re.match(r'Representative in Congress District', stripped):
        return 'U.S. House'
    if re.match(r'Senator in General Assembly', stripped):
        return 'State Senate'
    if re.match(r'Representative in General Assembly', stripped):
        return 'State House'
    if stripped in OFFICE_MAP:
        return OFFICE_MAP[stripped]
    return stripped

def extract_district(title):
    m = re.search(r'\bDistrict\s+(\d+)', title, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'\bWard\s+(\d+)', title, re.IGNORECASE)
    if m:
        return m.group(1)
    return ''

def get_town(precinct_name):
    # Format is "Town Name XXXX" where XXXX is a 4-digit precinct number
    parts = precinct_name.rsplit(' ', 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
        return parts[0]
    return precinct_name

def parse_long_record(line):
    party = line[101:104].strip()
    candidate = line[167:205].strip()
    # Some candidate names are prefixed with the party code (e.g. "DEM John Smith")
    if party and candidate.startswith(party + ' '):
        candidate = candidate[len(party) + 1:].strip()
    return {
        'total_votes':  int(line[11:17]) if line[11:17].strip() else 0,
        'election_day': int(line[17:23]) if line[17:23].strip() else 0,
        'mail':         int(line[23:29]) if line[23:29].strip() else 0,
        'early_voting': int(line[29:35]) if line[29:35].strip() else 0,
        'party':        party,
        'contest':      line[111:167].strip(),
        'candidate':    candidate,
        'precinct':     line[205:235].strip(),
    }

def build_lookup(setup_zip_bytes):
    """Build a (contest, candidate, precinct) -> descriptive fields lookup from
    the long-format setup file contained in the given zip bytes."""
    z = zipfile.ZipFile(io.BytesIO(setup_zip_bytes))
    setup_name = next(
        name for name in z.namelist()
        if name.lower().endswith(('.txt', '.asc')) and not name.startswith('__')
        and 'setup' not in name.lower() and '/' not in name
    )
    lookup = {}
    with z.open(setup_name) as f:
        for raw in f:
            line = raw.decode('latin-1').rstrip('\r\n')
            if len(line) < 235:
                continue
            key = (line[0:4], line[4:7], line[7:11])
            party = line[101:104].strip()
            candidate = line[167:205].strip()
            if party and candidate.startswith(party + ' '):
                candidate = candidate[len(party) + 1:].strip()
            lookup[key] = {
                'party':     party,
                'contest':   line[111:167].strip(),
                'candidate': candidate,
                'precinct':  line[205:235].strip(),
            }
    return lookup

def parse_short_record(line, lookup):
    key = (line[0:4], line[4:7], line[7:11])
    meta = lookup.get(key, {})
    return {
        'total_votes':  int(line[11:17]) if line[11:17].strip() else 0,
        'election_day': int(line[17:23]) if line[17:23].strip() else 0,
        'mail':         int(line[23:29]) if line[23:29].strip() else 0,
        'early_voting': int(line[29:35]) if line[29:35].strip() else 0,
        'party':        meta.get('party', ''),
        'contest':      meta.get('contest', ''),
        'candidate':    meta.get('candidate', ''),
        'precinct':     meta.get('precinct', ''),
    }

def accumulate(totals, rec, by_precinct=False):
    town = get_town(rec['precinct'])
    precinct = rec['precinct'] if by_precinct else None
    office = normalize_office(rec['contest'])
    district = extract_district(rec['contest'])
    key = (town, precinct, office, district, rec['party'], rec['candidate'])
    prev = totals.get(key, (0, 0, 0, 0))
    totals[key] = (
        prev[0] + rec['total_votes'],
        prev[1] + rec['election_day'],
        prev[2] + rec['mail'],
        prev[3] + rec['early_voting'],
    )

def write_csv(totals, output_path, by_precinct=False):
    with open(output_path, 'wt', newline='') as csvfile:
        w = csv.writer(csvfile)
        if by_precinct:
            w.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'election_day', 'mail', 'early_voting'])
            for (town, precinct, office, district, party, candidate), (votes, election_day, mail, early_voting) in sorted(totals.items()):
                w.writerow([town, precinct, office, district, party, candidate, votes, election_day, mail, early_voting])
        else:
            w.writerow(['county', 'office', 'district', 'party', 'candidate', 'votes', 'election_day', 'mail', 'early_voting'])
            for (town, _precinct, office, district, party, candidate), (votes, election_day, mail, early_voting) in sorted(totals.items()):
                w.writerow([town, office, district, party, candidate, votes, election_day, mail, early_voting])

def parse_long(url, output_path, by_precinct=False):
    r = requests.get(url)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    results_name = next(
        name for name in z.namelist()
        if name.lower().endswith(('.txt', '.asc')) and not name.startswith('__')
        and 'setup' not in name.lower() and '/' not in name
    )
    totals = {}
    with z.open(results_name) as f:
        for raw in f:
            line = raw.decode('latin-1').rstrip('\r\n')
            if len(line) < 235:
                continue
            accumulate(totals, parse_long_record(line), by_precinct)
    write_csv(totals, output_path, by_precinct)

def parse_short(url, long_url, output_path, by_precinct=False):
    long_r = requests.get(long_url)
    long_r.raise_for_status()
    lookup = build_lookup(long_r.content)

    r = requests.get(url)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    results_name = next(
        name for name in z.namelist()
        if name.lower().endswith(('.txt', '.asc')) and not name.startswith('__')
        and 'setup' not in name.lower() and '/' not in name
    )
    totals = {}
    with z.open(results_name) as f:
        for raw in f:
            line = raw.decode('latin-1').rstrip('\r\n')
            if len(line) < 35:
                continue
            rec = parse_short_record(line, lookup)
            if rec['contest']:
                accumulate(totals, rec, by_precinct)
    write_csv(totals, output_path, by_precinct)


# Maps --election-type value to (url_path, file_prefix, csv_label)
ELECTION_TYPES = {
    'general':              ('general_election',               'rigen',     'general'),
    'primary':              ('statewide_primary',              'ripri',     'primary'),
    'presidential-primary': ('presidential_preference_primary', 'ppp',      'primary__president'),
    'special':              ('special_election',               'rispecial', 'special'),
}

def long_url_for_year(year, election_type='general'):
    url_path, prefix, _ = ELECTION_TYPES[election_type]
    return f"https://www.ri.gov/election/results/{year}/{url_path}/data/{prefix}{year}l.zip"

def short_url_for_year(year, election_type='general'):
    url_path, prefix, _ = ELECTION_TYPES[election_type]
    return f"https://www.ri.gov/election/results/{year}/{url_path}/data/{prefix}{year}.zip"

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse RI election results into OpenElections CSV format."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--year', metavar='YEAR', help='Election year (e.g. 2024); constructs URLs automatically')
    source.add_argument('--url', metavar='URL', help='Direct URL to a long-format zip file')

    parser.add_argument('--short-url', metavar='URL',
                        help='Short-format zip URL (requires --url or --year to provide the long-format lookup)')
    parser.add_argument('--election-type', metavar='TYPE', default='general',
                        choices=ELECTION_TYPES.keys(),
                        help='Election type: general (default), primary, presidential-primary')
    parser.add_argument('--date', metavar='YYYYMMDD',
                        help='Election date for the output filename (e.g. 20241105); used with --year')
    parser.add_argument('--output', metavar='PATH',
                        help='Output CSV path (default: derived from date/year in the current directory)')
    parser.add_argument('--precinct', action='store_true',
                        help='Output precinct-level results instead of town totals')
    args = parser.parse_args()

    election_type = args.election_type
    _, _, csv_label = ELECTION_TYPES[election_type]
    geo = 'precinct' if args.precinct else 'town'

    if args.year:
        long = long_url_for_year(args.year, election_type)
        short = short_url_for_year(args.year, election_type)
        date_prefix = args.date or args.year
        year = args.year
    else:
        long = args.url
        short = args.short_url
        date_prefix = args.date or 'results'
        year = args.date[:4] if args.date else None

    filename = f"{date_prefix}__ri__{csv_label}__{geo}.csv"
    if args.output:
        output = args.output
    elif year:
        year_dir = os.path.join(os.path.dirname(__file__), year)
        os.makedirs(year_dir, exist_ok=True)
        output = os.path.join(year_dir, filename)
    else:
        output = filename

    if args.short_url or (args.year and short):
        parse_short(short, long, output, args.precinct)
    else:
        parse_long(long, output, args.precinct)

    print(f"Written: {output}")

if __name__ == '__main__':
    main()
