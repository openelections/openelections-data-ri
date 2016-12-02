rigen2016l.zip:
	curl -o rigen2016l.zip "https://www.ri.gov/election/results/2016/general_election/data/rigen2016l.zip"

rigen2016l.asc: rigen2016l.zip
	unzip rigen2016l.zip
	touch rigen2016l.asc

20161108__ri__general__precinct.csv: rigen2016l.asc
	python2 converter.py
