import re
import csv

def convert():
    with open("20201103__ri__general__precinct.csv", "wt") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(['office', 'district', 'candidate', 'party', 'precinct', 'votes', 'absentee_votes'])
        for line in get_lines():
            #Process the line
            result = process_line(line)
            #If the race is not of interest to us, continue
            if not result:
                continue
            w.writerow(result)

#A function to process a single line
#All line position indices are from https://www.ri.gov/election/results/20160902_data_description.pdf
def process_line(line):
    #Get the long title of the race and then shorten it
    race_long = line[111:167]
    race_short = race_shortener(race_long)
    if not race_short:
        #If race_name returns false, we don't care about the race, so return false
        return False
    #Get the district name and then shorten it
    district = line[235:260]
    district_num = district_shortener(district)
    #Get the candidate name, removing trailing whitespace
    candidate = line[167:205].rstrip()
    #Get the party name and shorten it
    party_long = line[101:104]
    party_short = party_shortener(party_long)
    #Get the precinct name, removing trailing whitespace
    precinct = line[205:235].rstrip()
    #Get the votes (all)
    votes = int(line[11:17])
    #Get just the mail ballots
    absentee_votes = int(line[23:29])

    #Return all of the values as a list
    return [race_short, district_num, candidate, party_short, precinct, votes, absentee_votes]



#A function which makes race names more reasonable
def race_shortener(long):
    if "Presidential Electors For" in long:
        return "President"
    elif "Senator in Congress" in long:
        return "U.S. Senate"
    elif "Representative in Congress" in long:
        return "U.S. House"
    elif "Senator in General Assembly" in long:
        return "State Senate"
    elif "Representative in General Assembly" in long:
        return "State House"
    elif "Lieutenant Governor" in long:
        return "Lieutenant Governor"
    elif "Governor" in long:
        return "Governor"
    elif "Secretary of State" in long:
        return "Secretary of State"
    elif "Attorney General" in long:
        return "Attorney General"
    elif "General Treasurer" in long:
        return "General Treasurer"
    else:
        #If it is isn't any of the above races, we don't care about it, so return False
        return False

#A function to shorten district names
def district_shortener(long):
    if "District" not in long:
        return None
    long = long.replace(" ", "")
    if long:
        try:
            num = re.findall('\d+', long)[0]
        except:
            num = None
    else:
        num = ''
    return num

#A function which shortens party names
def party_shortener(long):
    if "REP" in long:
        return "R"
    elif "DEM" in long:
        return "D"
    elif "Lib" in long:
        return "L"
    elif "Grn" in long:
        return "G"
    elif "Ind" in long:
        return "I"
    else:
        return ""

def get_lines():
    with open("rigen2020l.asc") as f:
        return f.readlines()

convert()
