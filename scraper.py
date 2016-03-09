import requests
import unicodecsv
from BeautifulSoup import BeautifulSoup

def parse():
    with open('20040302__ri__primary__president.csv', 'wb') as csvfile:
        w = unicodecsv.writer(csvfile, encoding='utf-8')
        for jurisdiction in _get_jurisdictions():
            r = requests.get("http://www.elections.ri.gov/elections/results/2004/preference/%s.php" % jurisdiction['slug'])
            soup = BeautifulSoup(r.text)
            for table in soup.findAll('table')[0:2]:
                w.writerow(_parse_table(table, jurisdiction))


def _parse_table(table, jurisdiction):
    results = []
    rows = table.findAll('tr')[1:]
    for row in rows:
        results.append([td.text for td in row.findAll('td')])
    return results

def _get_jurisdictions():
    with open('jurisdictions.csv', 'rU') as csvfile:
        reader = unicodecsv.DictReader(csvfile)
        return [row for row in reader]
