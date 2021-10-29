import requests
import xml.etree.ElementTree as ET

# get data
base_string = "http://isni.oclc.org/sru/?query=pica.na+%3D+%22"
suffix_string = "%22&version=1.1&operation=searchRetrieve&recordSchema=isni-b&maximumRecords=10&startRecord=1&recordPacking=xml&sortKeys=RLV%2Cpica%2C0%2C%2C"


def url_stringify(string):
    return string.replace(" ", "+")


def find_authors_by_name(names):

    names = url_stringify(names)
    query = base_string + names + suffix_string
    r = requests.get(query)
    # parse xml
    payload = r.text
    root = ET.fromstring(payload)

    # build list of possible authors
    possible_authors = []
    for el in root.iter("responseRecord"):

        author = dict()
        author["uri"] = el.find(".//isniURI").text
        # NOTE: this will often be incorrect, some naming systems list "surname" before personal name
        personal_name = el.find(".//forename/..")
        forename = personal_name.find(".//forename")
        surname = personal_name.find(".//surname")
        author["name"] = surname.text
        if personal_name:
            author["name"] = forename.text + " " + surname.text
            author["description"] = el.find(".//nameTitle").text

            possible_authors.append(author)

    return possible_authors
