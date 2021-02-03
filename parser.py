import csv
import requests

towns = ['Barrington','Bristol','Burrillville','Central Falls','Charlestown','Coventry','Cranston','Cumberland','East Greenwich','East Providence','Exeter','Foster',
'Glocester','Hopkinton','Jamestown','Johnston','Lincoln','Little Compton','Middletown','Narragansett','New Shoreham','Newport','North Kingstown','North Providence',
'North Smithfield','Pawtucket','Portsmouth','Providence','Richmond','Scituate','Smithfield','South Kingstown','Tiverton','Warren','Warwick','West Greenwich','West Warwick',
'Westerly','Woonsocket']

results = []

for town in towns:
    url = "https://rigov.s3.amazonaws.com/election/results/2020/statewide_primary/%s.json" % town.lower().replace(' ','_')
    r = requests.get(url)
    contests = r.json()['contests']
    for contest in contests:
        office = contest['name']
        total_votes = contest['total_votes']
        results.append([town, office, None, None, 'Total', total_votes])
        for candidate in contest['candidates']:
            results.append([town, office, None, candidate['party_code'], candidate['name'], candidate['votes']])

with open("20200908__ri__primary__town.csv", "wt") as csvfile:
    w = csv.writer(csvfile)
    w.writerow(['county', 'office', 'district', 'party', 'candidate', 'votes'])
    w.writerows(results)
