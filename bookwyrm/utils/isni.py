"""ISNI author checking utilities"""
import xml.etree.ElementTree as ET
import requests


def url_stringify(string):
    """replace spaces for url encoding"""

    # TODO: this is very lazy and incomplete
    return string.replace(" ", "+")


def request_isni_data(search_index, search_term, max_records=5):
    """Request data from the ISNI API"""

    search_string = url_stringify(search_term)
    query_parts = [
        "http://isni.oclc.org/sru/?query=",
        search_index,
        "+%3D+%22",
        search_string,
        "%22&version=1.1&operation=searchRetrieve&recordSchema=isni-b",
        "&maximumRecords=",
        str(max_records),
        "&startRecord=1&recordPacking=xml&sortKeys=RLV%2Cpica%2C0%2C%2C",
    ]
    query_url = "".join(query_parts)
    result = requests.get(query_url)
    # the OCLC ISNI server asserts the payload is encoded
    # in latin1, but we know better
    result.encoding = "utf-8"
    return result.text


def make_name_string(element):
    """create a string of form 'personal_name surname'"""

    # NOTE: this will often be incorrect, many naming systems
    # list "surname" before personal name
    forename = element.find(".//forename")
    surname = element.find(".//surname")
    if forename is not None:
        return "".join([forename.text, " ", surname.text])
    return surname.text


def get_other_identifier(element, code):
    """Get other identifiers associated with an author from their ISNI record"""

    identifiers = element.findall(".//otherIdentifierOfIdentity")
    for section_head in identifiers:
        if (
            section_head.find(".//type") is not None
            and section_head.find(".//type").text == code
            and section_head.find(".//identifier") is not None
        ):
            return section_head.find(".//identifier").text
    return ""


def get_external_information_uri(element, match_string):
    """Get URLs associated with an author from their ISNI record"""

    sources = element.findall(".//externalInformation")
    for source in sources:
        uri = source.find(".//URI")
        if uri is not None and uri.text.find(match_string) is not None:
            return uri.text
    return ""


def find_authors_by_name(name_string):
    """Query the ISNI database for possible author matches by name"""

    payload = request_isni_data("pica.na", name_string)
    # parse xml
    root = ET.fromstring(payload)
    # build list of possible authors
    possible_authors = []
    for element in root.iter("responseRecord"):

        personal_name = element.find(".//forename/..")
        bio = element.find(".//nameTitle")

        if not personal_name:
            continue

        author = {}
        author["isni"] = element.find(".//isniUnformatted").text
        author["uri"] = element.find(".//isniURI").text
        author["name"] = make_name_string(personal_name)
        if bio is not None:
            author["bio"] = bio.text
        possible_authors.append(author)

    return possible_authors


def get_author_isni_data(isni):
    """Find data to populate a new author record from their ISNI"""

    payload = request_isni_data("pica.isn", isni)
    # parse xml
    root = ET.fromstring(payload)
    # there should only be a single responseRecord
    # but let's use the first one just in case
    element = root.find(".//responseRecord")
    personal_name = element.find(".//forename/..")
    bio = element.find(".//nameTitle")
    author = {}
    author["isni"] = isni
    author["name"] = make_name_string(personal_name)
    author["viaf_id"] = get_other_identifier(element, "viaf")
    author["wikipedia_link"] = get_external_information_uri(element, "Wikipedia")
    author["bio"] = bio.text if bio is not None else ""
    author["aliases"] = []
    aliases = element.findall(".//personalNameVariant")
    for entry in aliases:
        author["aliases"].append(make_name_string(entry))
    # dedupe aliases
    author["aliases"] = list(set(author["aliases"]))
    return author


def build_author_dict(match_value):
    """Build dict with basic author details from ISNI or author name"""

    # if it is an isni value get the data
    if match_value.startswith("isni_match_"):
        isni = match_value.replace("isni_match_", "")
        return get_author_isni_data(isni)
    # otherwise it's a name string
    return {"name": match_value}


def augment_author_metadata(author, isni):
    """Update any missing author fields from ISNI data"""
    isni_data = get_author_isni_data(isni)
    author.viaf_id = (
        isni_data["viaf_id"] if len(author.viaf_id) == 0 else author.viaf_id
    )
    author.wikipedia_link = (
        isni_data["wikipedia_link"]
        if len(author.wikipedia_link) == 0
        else author.wikipedia_link
    )
    author.bio = isni_data["bio"] if len(author.bio) == 0 else author.bio
    aliases = set(isni_data["aliases"])
    for alias in author.aliases:
        aliases.add(alias)
    author.aliases = list(aliases)
    author.save()
