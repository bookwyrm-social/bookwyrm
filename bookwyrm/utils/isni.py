"""ISNI author checking utilities"""
import xml.etree.ElementTree as ET
import requests

from bookwyrm import activitypub, models

def request_isni_data(search_index, search_term, max_records=5):
    """Request data from the ISNI API"""

    search_string = f'{search_index}="{search_term}"'
    query_params = {
        "query": search_string,
        "version": "1.1",
        "operation": "searchRetrieve",
        "recordSchema": "isni-b",
        "maximumRecords": max_records,
        "startRecord": "1",
        "recordPacking": "xml",
        "sortKeys": "RLV,pica,0,,",
    }
    result = requests.get(
      "http://isni.oclc.org/sru/", 
      params=query_params,
      timeout=10
      )
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

    # if we can't find it in otherIdentifierOfIdentity,
    # try sources
    for source in element.findall(".//sources"):
        code_of_source = source.find(".//codeOfSource")
        if (
            code_of_source is not None 
            and code_of_source.text == code.upper()
            or code_of_source.text == code.lower()
            ):
            return source.find(".//sourceIdentifier").text

    return ""


def get_external_information_uri(element, match_string):
    """Get URLs associated with an author from their ISNI record"""

    sources = element.findall(".//externalInformation")
    for source in sources:
        information = source.find(".//information")
        uri = source.find(".//URI")
        if (
          uri is not None 
          and information is not None
          and information.text.lower() == match_string.lower()
          ):
            return uri.text
    return ""


def find_authors_by_name(name_string, description=False):
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

        author = get_author_from_isni(element.find(".//isniUnformatted").text)

        if bool(description):
            titles = element.findall(".//title")
            if titles:
                # some of the "titles" in ISNI are a little ...iffy
                title_element = [e for e in titles if not e.text.replace('@', '').isnumeric()][0]
            title = (
              title_element.text.replace('@', '')
              if titles is not None
              and title_element is not None
              and len(title_element.text) > 4
              else None
            )
            author.bio = (
              title if title is not None
              else bio.text if bio is not None
              else "More information at isni.org"
            )

        possible_authors.append(author)

    return possible_authors


def get_author_from_isni(isni):
    """Find data to populate a new author record from their ISNI"""

    payload = request_isni_data("pica.isn", isni)
    # parse xml
    root = ET.fromstring(payload)
    # there should only be a single responseRecord
    # but let's use the first one just in case
    element = root.find(".//responseRecord")
    name = make_name_string(element.find(".//forename/.."))
    viaf = get_other_identifier(element, "viaf")
    # use a set to dedupe aliases in ISNI
    aliases = set()
    aliases_element = element.findall(".//personalNameVariant")
    for entry in aliases_element:
        aliases.add(make_name_string(entry))
    # aliases needs to be list not set
    aliases = list(aliases)
    bio = element.find(".//nameTitle")
    bio = bio.text if bio is not None else ""
    wikipedia = get_external_information_uri(element, "Wikipedia")

    author = activitypub.Author(
      id=element.find(".//isniURI").text,
      name=name,
      isni=isni,
      viafId=viaf,
      aliases=aliases,
      bio=bio,
      wikipediaLink=wikipedia
    )

    return author

def build_author_from_isni(match_value):
    """Build dict with basic author details from ISNI or author name"""

    # if it is an isni value get the data
    if match_value.startswith("https://isni.org/isni/"):
        isni = match_value.replace("https://isni.org/isni/", "")
        return { "author": get_author_from_isni(isni) }
    # otherwise it's a name string
    return {}


def augment_author_metadata(author, isni):
    """Update any missing author fields from ISNI data"""

    isni_author = get_author_from_isni(isni)
    isni_author.to_model(model=models.Author, instance=author, overwrite=False)

    # we DO want to overwrite aliases because we're adding them to the 
    # existing aliases and ISNI will usually have more.
    # We need to dedupe because ISNI records often have lots of dupe aliases
    aliases = set(isni_author["aliases"])
    for alias in author.aliases:
        aliases.add(alias)
    author.aliases = list(aliases)
    author.save()

    return
