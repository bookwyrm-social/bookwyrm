"""ISNI author checking utilities"""
import xml.etree.ElementTree as ET
import requests

# get data
BASE_STRING = "http://isni.oclc.org/sru/?query=pica.na+%3D+%22"
SUFFIX_STRING = "%22&version=1.1&operation=searchRetrieve&recordSchema=isni-b&maximumRecords=10&startRecord=1&recordPacking=xml&sortKeys=RLV%2Cpica%2C0%2C%2C"


def url_stringify(string):
    """replace spaces for url encoding"""
    return string.replace(" ", "+")


def find_authors_by_name(names):
    """Query the ISNI database for an author"""
    names = url_stringify(names)
    query = BASE_STRING + names + SUFFIX_STRING
    result = requests.get(query)
    # the OCLC ISNI server asserts the payload is encoded
    # in latin1, but we know better
    result.encoding = "utf-8"
    payload = result.text
    # parse xml
    root = ET.fromstring(payload)

    # build list of possible authors
    possible_authors = []
    for element in root.iter("responseRecord"):

        author = {}
        author["uri"] = element.find(".//isniURI").text
        # NOTE: this will often be incorrect, some naming systems list "surname" before personal name
        personal_name = element.find(".//forename/..")
        forename = personal_name.find(".//forename")
        surname = personal_name.find(".//surname")
        author["name"] = surname.text
        if personal_name:
            author["name"] = forename.text + " " + surname.text
            author["description"] = element.find(".//nameTitle").text

            possible_authors.append(author)

    return possible_authors
